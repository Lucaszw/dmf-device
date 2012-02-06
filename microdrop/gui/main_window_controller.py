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

import os
import sys
import gtk
import time
import webbrowser

from utility import wrap_string, is_float
from plugin_manager import ExtensionPoint, IPlugin, SingletonPlugin, \
    implements, emit_signal, PluginGlobals, ILoggingPlugin
from gui.plugin_manager_dialog import PluginManagerDialog
from app_context import get_app
from logger import logger


class MicroDropError(Exception):
    pass


PluginGlobals.push_env('microdrop')


class MainWindowController(SingletonPlugin):
    implements(IPlugin)
    implements(ILoggingPlugin)

    def __init__(self):
        self.name = "microdrop.gui.main_window_controller"
        self.builder = None
        self.view = None
        self.label_connection_status = None
        self.label_experiment_id = None
        self.label_device_name = None
        self.label_protocol_name = None
        self.checkbutton_realtime_mode = None
        self.menu_tools = None
        self.menu_view = None
        gtk.link_button_set_uri_hook(self.on_url_clicked)
        
        builder = gtk.Builder()
        builder.add_from_file(os.path.join("gui",
                              "glade",
                              "text_input_dialog.glade"))
        self.text_input_dialog = builder.get_object("window")
        self.text_input_dialog.textentry = builder.get_object("textentry")
        self.text_input_dialog.label = builder.get_object("label")
        
    def on_app_init(self):
        #print '[MainWindowController] %s' % get_app()
        app = get_app()
        app.builder.add_from_file(os.path.join("gui",
                                               "glade",
                                               "main_window.glade"))
        self.view = app.builder.get_object("window")
        self.label_connection_status = app.builder.get_object("label_connection_status")
        self.label_experiment_id = app.builder.get_object("label_experiment_id")
        self.label_device_name = app.builder.get_object("label_device_name")
        self.label_protocol_name = app.builder.get_object("label_protocol_name")
        self.checkbutton_realtime_mode = app.builder.get_object("checkbutton_realtime_mode")
        self.menu_tools = app.builder.get_object("menu_tools")
        self.menu_view = app.builder.get_object("menu_view")

        app.signals["on_menu_quit_activate"] = self.on_destroy
        app.signals["on_menu_about_activate"] = self.on_about
        app.signals["on_menu_online_help_activate"] = self.on_menu_online_help_activate
        app.signals["on_menu_experiment_logs_activate"] = \
            self.on_menu_experiment_logs_activate
        app.signals["on_window_destroy"] = self.on_destroy
        app.signals["on_window_delete_event"] = self.on_delete_event
        app.signals["on_checkbutton_realtime_mode_toggled"] = \
                self.on_realtime_mode_toggled
        app.signals["on_menu_options_activate"] = self.on_menu_options_activate
        app.signals["on_menu_manage_plugins_activate"] = self.on_menu_manage_plugins_activate
        app.signals["on_menu_debug_activate"] = self.on_menu_debug_activate

        self.builder = gtk.Builder()
        self.builder.add_from_file(os.path.join("gui",
                                                "glade",
                                                "about_dialog.glade"))
        app.main_window_controller = self
        self.protocol_list_view = None
        
    def main(self):
        self.update()
        gtk.main()

    def get_text_input(self, title, label, default_value=""):
        self.text_input_dialog.set_title(title)
        self.text_input_dialog.label.set_markup(label)
        self.text_input_dialog.textentry.set_text(default_value)
        self.text_input_dialog.set_transient_for(self.view)
        response = self.text_input_dialog.run()
        self.text_input_dialog.hide()
        name = ""
        if response == gtk.RESPONSE_OK:
            name = self.text_input_dialog.textentry.get_text()
        return name

    def on_delete_event(self, widget, data=None):
        emit_signal("on_app_exit")

    def on_destroy(self, widget, data=None):
        gtk.main_quit()
        observers = ExtensionPoint(IPlugin)
        service = observers.service('microdrop.gui.video_controller')
        service.on_plugin_disable()
        service.__del__()

    def on_about(self, widget, data=None):
        app = get_app()
        dialog = self.builder.get_object("about_dialog")
        dialog.set_transient_for(app.main_window_controller.view)
        dialog.set_version(app.version)
        dialog.run()
        dialog.hide()

    def on_menu_online_help_activate(self, widget, data=None):
        webbrowser.open_new_tab('http://microfluidics.utoronto.ca/microdrop/wiki/UserGuide')

    def on_menu_manage_plugins_activate(self, widget, data=None):
        app = get_app()
        pmd = PluginManagerDialog()
        response = pmd.run()

    def on_menu_debug_activate(self, widget, data=None):
        app = get_app()
        step = app.protocol.current_step()
        dmf_plugin_name = step.plugin_name_lookup(
            r'wheelerlab.dmf_control_board_', re_pattern=True)
        logger.info('[MainWindowController] Menu debug activated')
        observers = ExtensionPoint(IPlugin)
        service = observers.service(dmf_plugin_name)
        import random
        service.set_step_values({'voltage': random.randint(10, 100),
                'frequency': random.randint(1e3, 100e3),
                'feedback_enabled': True})
        self.update()

    def on_menu_experiment_logs_activate(self, widget, data=None):
        app = get_app()
        app.experiment_log_controller.on_window_show(widget, data)

    def on_realtime_mode_toggled(self, widget, data=None):
        self.update()

    def on_menu_options_activate(self, widget, data=None):
        from options_controller import OptionsController

        OptionsController().run()
        self.update()

    def on_warning(self, record):
        self.warning(record.message)

    def on_error(self, record):
        self.error(record.message)

    def on_critical(self, record):
        self.error(record.message)

    def error(self, message, title="Error"):
        dialog = gtk.MessageDialog(self.view,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_ERROR, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.set_title(title)
        result = dialog.run()
        dialog.destroy()
        return result

    def warning(self, message, title="Warning"):
        dialog = gtk.MessageDialog(self.view,
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_WARNING, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.set_title(title)
        result = dialog.run()
        dialog.destroy()
        return result

    def question(self, message, title=""):
        dialog = gtk.MessageDialog(self.view, 
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_QUESTION,
                                   gtk.BUTTONS_YES_NO, message)
        dialog.set_title(title)
        result = dialog.run()
        dialog.destroy()
        return result

    def info(self, message, title=""):
        dialog = gtk.MessageDialog(self.view, 
                                   gtk.DIALOG_DESTROY_WITH_PARENT,
                                   gtk.MESSAGE_INFO, 
                                   gtk.BUTTONS_CLOSE, message)
        dialog.set_title(title)
        result = dialog.run()
        dialog.destroy()
        return result

    def update(self):
        app = get_app()
        app.realtime_mode = self.checkbutton_realtime_mode.get_active()
        emit_signal("on_dmf_device_update")
        emit_signal("on_protocol_update")
        
        if app.dmf_device.name:
            experiment_id = app.experiment_log.get_next_id()
        else:
            experiment_id = None
        self.label_experiment_id.set_text("Experiment: %s" % str(experiment_id))
        self.label_device_name.set_text("Device: %s" % app.dmf_device.name)
        self.label_protocol_name.set_text(
                wrap_string("Protocol: %s" % app.protocol.name, 30, "\n\t"))
        
        # process all gtk events
        while gtk.events_pending():
            gtk.main_iteration()

    def on_url_clicked(self, widget, data):
        logger.debug("URL clicked: %s" % data)
        webbrowser.open_new_tab(data)

    def on_protocol_changed(self, protocol):
        self.update()

PluginGlobals.pop_env()
