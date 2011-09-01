"""
Copyright 2011 Ryan Fobel

This file is part of Microdrop.

Microdrop is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Microdrop is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Microdrop.  If not, see <http://www.gnu.org/licenses/>.
"""

import os, gtk, time, subprocess
import numpy as np
from hardware.dmf_control_board import DmfControlBoard
from hardware.agilent_33220a import Agilent33220A
from gui.main_window_controller import MainWindowController
from gui.dmf_device_controller import DmfDeviceController
from gui.protocol_controller import ProtocolController
from gui.config_controller import ConfigController
from gui.experiment_log_controller import ExperimentLogController
from config import load as load_config
from experiment_log import ExperimentLog

class App:
    def __init__(self):
        # get the version number
        try:
            self.version = subprocess.Popen(['git','describe'],
                           stdout=subprocess.PIPE).communicate()[0].rstrip()
        except:
            self.version = "0.1"
        self.realtime_mode = False
        self.is_running = False
        self.builder = gtk.Builder()
        signals = {}
        
        # models
        self.config = load_config()
        self.dmf_device = self.config.load_dmf_device()
        self.protocol = self.config.load_protocol()
        self.control_board = DmfControlBoard()
        #self.control_board.set_debug(True)
        self.func_gen = Agilent33220A()
        device_path = None
        if self.dmf_device.name:
            device_path = os.path.join(self.config.dmf_device_directory,
                                       self.dmf_device.name, "logs")
        self.experiment_log = ExperimentLog(device_path)

        # controllers
        self.config_controller = ConfigController(self)
        self.main_window_controller = MainWindowController(self, self.builder, signals)
        self.dmf_device_controller = DmfDeviceController(self, self.builder, signals)
        self.protocol_controller = ProtocolController(self, self.builder, signals)
        self.experiment_log_controller = ExperimentLogController(self)

        self.builder.connect_signals(signals)
        self.main_window_controller.main()

    def run_protocol(self):
        self.is_running = True
        self.run_step()

    def pause_protocol(self):
        self.is_running = False
        
    def run_step(self):
        self.main_window_controller.update()
        if self.control_board.connected():
            data = {"step":self.protocol.current_step_number,
                    "time":time.time()}
            feedback_options = \
                self.protocol.current_step().feedback_options
            state = self.protocol.current_step().state_of_channels
            if feedback_options: # run this step with feedback
                ad_channel = 1

                # measure droplet impedance
                self.control_board.set_series_resistor(ad_channel, 2)
                
                impedance = self.control_board.MeasureImpedance(
                           feedback_options.sampling_time_ms,
                           feedback_options.n_samples,
                           feedback_options.delay_between_samples_ms,
                           state)
                V_fb = impedance[0::2]
                Z_fb = impedance[1::2]
                V_total = self.protocol.current_step().voltage
                Z_device = Z_fb*(V_total/V_fb-1)
                data["Z_device"] = Z_device
                data["V_fb"] = V_fb
                data["Z_fb"] = Z_fb

                """
                # measure the voltage waveform for each series resistor
                for i in range(0,4):
                    self.control_board.set_series_resistor(ad_channel,i)
                    voltage_waveform = self.control_board.SampleVoltage(
                                [ad_channel], 1000, 1, 0, state)
                    data["voltage waveform (Resistor=%.1f kOhms)" %
                         (self.control_board.series_resistor(ad_channel)/1000.0)] = \
                         voltage_waveform
                """
            else:   # run without feedback
                self.control_board.set_state_of_all_channels(state)
                time.sleep(self.protocol.current_step().time/1000.0)

            """
            # TODO: temproary hack to measure temperature
            state = np.zeros(len(state))
            voltage_waveform = self.control_board.SampleVoltage(
                        [15], 10, 1, 0, state)
            temp = np.mean(voltage_waveform/1024.0*5.0/0.01)
            print temp
            data["AD595 temp"] = temp
            """
            
            self.experiment_log.add_data(data)
        else: # run through protocol (even though device is not connected)
                time.sleep(self.protocol.current_step().time/1000.0)
        
        if self.protocol.current_step_number < len(self.protocol)-1:
            self.protocol.next_step()
        elif self.protocol.current_repetition < self.protocol.n_repeats-1:
            self.protocol.next_repetition()
        else: # we're on the last step
            self.is_running = False
            self.experiment_log_controller.save()

        if self.is_running:
            self.run_step()
        
if __name__ == '__main__':
    app = App()