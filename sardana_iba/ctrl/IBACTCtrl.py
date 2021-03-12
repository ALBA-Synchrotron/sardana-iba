#!/usr/bin/env python

#############################################################################
#
# file :        ImgBeamAanalyzerController.py
#
# description :
#
# project :     Sardana/Pool/ctrls/countertimer
#
# developers history: sblanch, rhoms
#
# copyleft :    Cells / Alba Synchrotron
#               Bellaterra
#               Spain
#
#############################################################################
#
# This file is part of Sardana.
#
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.
###########################################################################

import PyTango
import time
from sardana import State
from sardana.pool.controller import CounterTimerController, Description, \
    Type, AcqSynch


class ImgBeamAnalyzerCTCtrl(CounterTimerController):
    """
    This class is the Tango Sardana CounterTimer controller for the
    Tango ImgBeamAnalyzer device. One controller only knows one device,
    and each counter channel responds to one specific device attribute.
    The controller works in event mode
    """

    ctrl_properties = {'devName': {Description: 'ImgBeamAnalyzer Tango device',
                              Type: str},
                  'attrList': {Description: 'List of attributes to read '
                                            'after the master channel space '
                                            'separated',
                               Type: str},
                  }

    # only one device, the ctrl device means attributes of one IBA
    MaxDevice = 1024

    kls = 'ImgBeamAnalyzerController'
    name = ''
    gender = 'ImgBeamAnalyzer Counter'
    model = 'ImgBeamAnalyzer_CT'
    image = ''
    icon = ''
    organization = 'CELLS - ALBA'
    logo = 'ALBA_logo.png'

    def __init__(self, inst, props, *args, **kwargs):
        CounterTimerController.__init__(self, inst, props, *args, **kwargs)
        self._state = State.On
        self._status = 'Status ON'
        self._latency_time = 0
        self._last_iba_img = None
        self._last_ccd_img = None
        self._int_time = None
        self._started = False
        self._attrs_values = {}
        self._axes_to_read = set()
        self._synchronization = AcqSynch.SoftwareTrigger
        try:
            # IBA:
            self._iba = PyTango.DeviceProxy(self.devName)

            # CCD:
            img_prop = self._iba.get_property("ImageDevice")
            self._ccdName = img_prop['ImageDevice'][0]
            # FIXME: if the iba is configured in a different tangoDB,
            # this ImageDevice name won't have it
            self._ccd = PyTango.DeviceProxy(self._ccdName)

            # Configure IBA Mode to EVENT
            prop_mode = self._iba.get_property('Mode')['Mode'][0]
            if prop_mode.lower() != 'event':
                self._log.warning('Changing %s Property Mode from %s to '
                                  'EVENT', self.devName, prop_mode)
                self._iba.put_property({'Mode': 'EVENT'})
                self._iba.Init()
                time.sleep(0.5)

            # manipulate the attrList to accept string arrays, and space
            # separated string
            self._attr_list = self.attrList.split()

        except Exception as e:
            self._log.error("%s::__init__() Exception: %s" % (self.kls,
                                                              str(e)))

    def AddDevice(self, axis):
        """ add each counter involved"""

        if axis > len(self._attr_list)+1:
            raise Exception("Not possible with the current length of "
                            "attributes in the property.")

    def DeleteDevice(self, axis):
        pass

    def StateAll(self):
        iba_img = self._iba.read_attribute('ImageCounter').value
        iba_state = self._iba.state()
        if iba_state != PyTango.DevState.RUNNING:
            self._state = State.Alarm
            self._status = '{} is not Running, is in {}'.format(
                self.devName, iba_state)
        elif self._started and iba_img <= self._last_iba_img:
            self._state = State.Moving
            self._status = 'Device is acquiring/processing'
            if self._last_ccd_img < self._ccd.read_attribute(
                    'ImageCounter').value:
                self._log.info('CCD finished but not IBA')
        else:
            self._state = State.On
            self._status = 'Device ready to acquire'

    def StateOne(self, ind):
        return self._state, self._status

    def LoadOne(self, ind, value, repetitions, latency_time):
        if self._synchronization not in [AcqSynch.SoftwareGate,
                                         AcqSynch.SoftwareTrigger]:
            raise RuntimeError('This controller only allows software '
                               'gate/trigger synchronization')

        self._int_time = value
        self._started = False
        self._axes_to_read = set()
        self._attrs_values = {}

    def PreStartOneCT(self, ind):
        """Prepare the iba and the ccd for the acquisition"""

        try:
            iba_state = self._iba.state()
            if iba_state != PyTango.DevState.RUNNING:
                self._iba.start()
            ccd_state = self._ccd.state()
            if ccd_state != PyTango.DevState.OPEN:
                self._ccd.stop()

            self._ccd.write_attribute('ExposureTime', self._int_time * 1000)
            self._ccd.write_attribute('TriggerMode', 0)
            self._last_ccd_img = self._ccd.read_attribute('ImageCounter').value
            self._last_iba_img = self._iba.read_attribute('ImageCounter').value

            return True
        except Exception as e:
            self._log.error("PreStartOneCT(%d) exception: %s", ind, e)
            return False

    def StartAllCT(self):
        """Open the ccd to acquire and make process this image by the iba."""
        self._ccd.Snap()
        self._started = True

    def AbortOne(self, ind):
        self._ccd.stop()
        self._stated = False

    def PreReadOne(self, axis):
        if axis == 1:
            return
        self._axes_to_read.add(axis-2)

    def ReadAll(self):
        if self._state != State.On:
            return
        attr_to_read = [self._attr_list[axis] for axis in self._axes_to_read]
        self._axes_to_read = set()
        values = self._iba.read_attributes(attr_to_read)
        self._attrs_values = {val.name.lower(): val.value for val in values}

    def ReadOne(self, axis):
        if self._state != State.On:
            return None

        if axis == 1:
            return self._int_time
        else:
            return self._attrs_values[self._attr_list[axis-2].lower()]
