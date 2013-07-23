#-*- coding:utf-8 -*-

"""
This file is part of OpenSesame.

OpenSesame is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

OpenSesame is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with OpenSesame.  If not, see <http://www.gnu.org/licenses/>.
"""

from PyQt4 import QtCore, QtGui
from libqtopensesame.misc import includes, config, _
from libqtopensesame.misc.config import cfg
from libqtopensesame.items import experiment
from libopensesame import debug, exceptions, misc
import libopensesame.exceptions
import libopensesame.experiment
import libopensesame.plugins
import libopensesame.misc
import os.path
import os
import sys
import time
import traceback
import subprocess

class qtopensesame(QtGui.QMainWindow):

	"""The main class of the OpenSesame GUI"""

	# Set to False for release!
	devmode = False

	def __init__(self, app, parent=None):

		"""
		Constructor. This does very little, except prepare the app to be shown
		as rapidly as possible. The actual GUI initialization is handled by
		resume_init().

		Arguments:
		app -- the QApplication

		Keyword arguments:
		parent -- a link to the parent window
		"""

		if sys.platform == 'darwin':
			# Workaround for Qt issue on OS X that causes QMainWindow to
			# hide when adding QToolBar, see
			# https://bugreports.qt-project.org/browse/QTBUG-4300
			QtGui.QMainWindow.__init__(self, parent, \
				QtCore.Qt.MacWindowToolBarButtonHint)
		else:
			QtGui.QMainWindow.__init__(self, parent)
		self.app = app
		self.first_show = True

	def resume_init(self):

		"""Resume GUI initialization"""

		from libopensesame import misc
		from libqtopensesame.widgets import pool_widget
		from libqtopensesame.ui import opensesame_ui
		from libqtopensesame.misc import theme, dispatch
		import platform
		import random

		# Initialize random number generator
		random.seed()

		# Check the filesystem encoding for debugging purposes
		debug.msg('filesystem encoding: %s' % misc.filesystem_encoding())

		# Restore the configuration
		self.restore_config()

		# Setup dispatch
		self.dispatch = dispatch.dispatch(self)

		# Setup the UI
		self.ui = opensesame_ui.Ui_opensesame_mainwindow()
		self.ui.setupUi(self)
		self.ui.toolbar_items.main_window = self
		self.ui.itemtree.main_window = self
		self.ui.table_variables.main_window = self
		self.ui.tabwidget.main_window = self

		# Set some initial variables
		self.current_path = None
		self.version = misc.version
		self.codename = misc.codename
		self.lock_refresh = False
		self.unsaved_changes = False

		# Parse the command line
		self.parse_command_line()

		# Load a theme
		self.theme = theme.theme(self, self.options._theme)

		# Determine the home folder
		self.home_folder = libopensesame.misc.home_folder()

		# Determine autosave_folder
		if not os.path.exists(os.path.join(self.home_folder, ".opensesame")):
			os.mkdir(os.path.join(self.home_folder, ".opensesame"))
		if not os.path.exists(os.path.join(self.home_folder, ".opensesame", \
			"backup")):
			os.mkdir(os.path.join(self.home_folder, ".opensesame", "backup"))
		self.autosave_folder = os.path.join(self.home_folder, ".opensesame", \
			"backup")

		# Set the filter-string for opening and saving files
		self.file_type_filter = \
			"OpenSesame files (*.opensesame.tar.gz *.opensesame);;OpenSesame script and file pool (*.opensesame.tar.gz);;OpenSesame script (*.opensesame)"

		# Set the window message
		self.window_message(_("Welcome to OpenSesame %s") % self.version)

		# Set the window icon
		self.setWindowIcon(self.theme.qicon("opensesame"))

		# Make the connections
		self.ui.itemtree.itemClicked.connect(self.open_item)
		self.ui.action_quit.triggered.connect(self.closeEvent)
		self.ui.action_new.triggered.connect(self.new_file)
		self.ui.action_open.triggered.connect(self.open_file)
		self.ui.action_save.triggered.connect(self.save_file)
		self.ui.action_save_as.triggered.connect(self.save_file_as)
		self.ui.action_run.triggered.connect(self.run_experiment)
		self.ui.action_run_in_window.triggered.connect( \
			self.run_experiment_in_window)
		self.ui.action_run_quick.triggered.connect(self.run_quick)
		self.ui.action_enable_auto_response.triggered.connect( \
			self.set_auto_response)
		self.ui.action_close_all_tabs.triggered.connect( \
			self.ui.tabwidget.close_all)
		self.ui.action_close_other_tabs.triggered.connect( \
			self.ui.tabwidget.close_other)
		self.ui.action_onetabmode.triggered.connect( \
			self.ui.tabwidget.toggle_onetabmode)
		self.ui.action_show_overview.triggered.connect(self.toggle_overview)
		self.ui.action_show_variable_inspector.triggered.connect( \
			self.refresh_variable_inspector)
		self.ui.action_show_pool.triggered.connect(self.refresh_pool)
		self.ui.action_show_stdout.triggered.connect(self.refresh_stdout)
		self.ui.action_help.triggered.connect( \
			self.ui.tabwidget.open_general_help)
		self.ui.action_about.triggered.connect(self.ui.tabwidget.open_about)
		self.ui.action_online_documentation.triggered.connect( \
			self.ui.tabwidget.open_osdoc)
		self.ui.action_check_for_update.triggered.connect(self.check_update)
		self.ui.action_open_autosave_folder.triggered.connect( \
			self.open_autosave_folder)
		self.ui.action_preferences.triggered.connect( \
			self.ui.tabwidget.open_preferences)
		self.ui.action_add_loop.triggered.connect(self.drag_loop)
		self.ui.action_add_sequence.triggered.connect(self.drag_sequence)
		self.ui.action_add_sketchpad.triggered.connect(self.drag_sketchpad)
		self.ui.action_add_feedback.triggered.connect(self.drag_feedback)
		self.ui.action_add_sampler.triggered.connect(self.drag_sampler)
		self.ui.action_add_synth.triggered.connect(self.drag_synth)
		self.ui.action_add_keyboard_response.triggered.connect( \
			self.drag_keyboard_response)
		self.ui.action_add_mouse_response.triggered.connect( \
			self.drag_mouse_response)
		self.ui.action_add_logger.triggered.connect(self.drag_logger)
		self.ui.action_add_inline_script.triggered.connect( \
			self.drag_inline_script)
		self.ui.button_help_stdout.clicked.connect( \
			self.ui.tabwidget.open_stdout_help)

		# Setup the overview area
		self.ui.dock_overview.show()
		self.ui.dock_overview.visibilityChanged.connect( \
			self.ui.action_show_overview.setChecked)

		# Setup the variable inspector
		self.ui.dock_variable_inspector.hide()
		self.ui.button_help_variables.clicked.connect( \
			self.ui.tabwidget.open_variables_help)
		self.ui.dock_variable_inspector.visibilityChanged.connect( \
			self.ui.action_show_variable_inspector.setChecked)
		self.ui.edit_variable_filter.textChanged.connect( \
			self.refresh_variable_inspector)

		# Setup the file pool
		self.ui.dock_pool.hide()
		self.ui.dock_pool.visibilityChanged.connect( \
			self.ui.action_show_pool.setChecked)
		self.ui.pool_widget = pool_widget.pool_widget(self)
		self.ui.dock_pool.setWidget(self.ui.pool_widget)

		# Uncheck the debug window button on debug window close
		self.ui.dock_stdout.visibilityChanged.connect( \
			self.ui.action_show_stdout.setChecked)

		# Initialize keyboard shortcuts
		self.ui.shortcut_itemtree = QtGui.QShortcut( \
			QtGui.QKeySequence(), self, self.ui.itemtree.setFocus)
		self.ui.shortcut_tabwidget = QtGui.QShortcut( \
			QtGui.QKeySequence(), self, self.ui.tabwidget.setFocus)
		self.ui.shortcut_stdout = QtGui.QShortcut( \
			QtGui.QKeySequence(), self, self.ui.edit_stdout.setFocus)
		self.ui.shortcut_variables = QtGui.QShortcut( \
			QtGui.QKeySequence(), self, \
			self.ui.edit_variable_filter.setFocus)
		self.ui.shortcut_pool = QtGui.QShortcut( \
			QtGui.QKeySequence(), self, \
			self.ui.pool_widget.ui.edit_pool_filter.setFocus)

		# Create the initial experiment

		self.experiment = experiment.experiment(self, "New experiment", \
			open(misc.resource(os.path.join("templates", \
				"default.opensesame")), "r").read())

		# Build the items toolbar
		self.set_status(_("Welcome to OpenSesame %s") % self.version)
		self.restore_state()
		self.refresh_plugins()
		self.start_autosave_timer()
		self.update_recent_files()
		self.clean_autosave()
		self.set_unsaved(False)

	def parse_command_line(self):

		"""Parse command line options"""

		import optparse

		parser = optparse.OptionParser( \
			"usage: opensesame [experiment] [options]", \
			version = "%s '%s'" % (self.version, self.codename))
		parser.set_defaults(debug=False)
		parser.set_defaults(run=False)
		parser.set_defaults(run_in_window=False)
		group = optparse.OptionGroup(parser, "Immediately run an experiment")
		group.add_option("-r", "--run", action="store_true", dest="run", \
			help="Run fullscreen")
		group.add_option("-w", "--run-in-window", action="store_true", \
			dest="run_in_window", help="Run in window")
		parser.add_option_group(group)
		group = optparse.OptionGroup(parser, "Miscellaneous options")
		group.add_option("-c", "--config", action="store", dest="_config", \
			help="Set a configuration option, e.g, '--config auto_update_check=False;scintilla_font_size=10'. For a complete list of configuration options, please refer to the source of config.py.")
		group.add_option("-t", "--theme", action="store", dest="_theme", \
			help="Specify a GUI theme")
		group.add_option("-d", "--debug", action="store_true", dest="debug", \
			help="Print lots of debugging messages to the standard output")
		group.add_option("-s", "--stack", action="store_true", dest="_stack", \
			help="Print stack trace (only in debug mode)")
		group.add_option("-p", "--preload", action="store_true", dest="preload", \
			help="Preload Python modules")
		group.add_option("--pylink", action="store_true", dest="pylink", \
			help="Load PyLink before PyGame (necessary for using the Eyelink plug-ins in non-dummy mode)")
		group.add_option("--ipython", action="store_true", dest="ipython", \
			help="Enable the IPython interpreter")
		group.add_option("--locale", action="store_true", dest="locale", \
			help="Specify localization")
		group.add_option("--catch-translatables", action="store_true", \
			dest="catch_translatables", help="Log all translatable text")
		group.add_option("--no-global-resources", action="store_true", dest="no_global_resources", \
			help="Do not use global resources on *nix")
		parser.add_option_group(group)
		self.options, args = parser.parse_args(sys.argv)
		if self.options.run and self.options.run_in_window:
			parser.error("Options -r / --run and -w / --run-in-window are mutually exclusive.")

	def restore_config(self):

		"""Restores the configuration settings, but doesn't apply anything"""

		debug.msg()
		settings = QtCore.QSettings("cogscinl", "opensesame")
		settings.beginGroup("MainWindow")
		config.restore_config(settings)
		settings.endGroup()

	def restore_state(self):

		"""Restore the current window to the saved state"""

		debug.msg()

		# Force configuration options that were set via the command line
		config.parse_cmdline_args(self.options._config)

		self.resize(cfg.size)
		self.move(cfg.pos)
		self.experiment.auto_response = cfg.auto_response

		# Set the keyboard shortcuts
		self.ui.shortcut_itemtree.setKey(QtGui.QKeySequence( \
			cfg.shortcut_itemtree))
		self.ui.shortcut_tabwidget.setKey(QtGui.QKeySequence( \
			cfg.shortcut_tabwidget))
		self.ui.shortcut_stdout.setKey(QtGui.QKeySequence(cfg.shortcut_stdout))
		self.ui.shortcut_pool.setKey(QtGui.QKeySequence(cfg.shortcut_pool))
		self.ui.shortcut_variables.setKey(QtGui.QKeySequence( \
			cfg.shortcut_variables))

		# Unpack the string with recent files and only remember those that exist
		self.recent_files = []
		for path in cfg.recent_files.split(";;"):
			if os.path.exists(path):
				debug.msg("adding recent file '%s'" % path)
				self.recent_files.append(path)
			else:
				debug.msg("missing recent file '%s'" % path)

		self.ui.action_enable_auto_response.setChecked( \
			self.experiment.auto_response)
		self.ui.action_onetabmode.setChecked(cfg.onetabmode)
		self.ui.action_compact_toolbar.setChecked( \
			cfg.toolbar_size == 16)
		self.ui.tabwidget.toggle_onetabmode()

		if cfg.toolbar_text:
			self.ui.toolbar_main.setToolButtonStyle( \
				QtCore.Qt.ToolButtonTextUnderIcon)
		else:
			self.ui.toolbar_main.setToolButtonStyle( \
				QtCore.Qt.ToolButtonIconOnly)
		self.set_style()
		self.theme.set_toolbar_size(cfg.toolbar_size)

	def restore_window_state(self):

		"""
		This is done separately from the rest of the restoration, because if we
		don't wait until the end, the window gets distorted again.
		"""

		self.restoreState(config.get_config('_initial_window_state'))
		self.restoreGeometry(config.get_config('_initial_window_geometry'))

	def save_state(self):

		"""Restores the state of the current window"""

		debug.msg()
		settings = QtCore.QSettings("cogscinl", "opensesame")
		settings.beginGroup("MainWindow")
		config.save_config(settings)
		settings.setValue("size", self.size())
		settings.setValue("pos", self.pos())
		settings.setValue("_initial_window_geometry", self.saveGeometry())
		settings.setValue("_initial_window_state", self.saveState())
		settings.setValue("auto_response", self.experiment.auto_response)
		settings.setValue("toolbar_text", \
			self.ui.toolbar_main.toolButtonStyle() == \
			QtCore.Qt.ToolButtonTextUnderIcon)
		settings.setValue("recent_files", ";;".join(self.recent_files))
		settings.endGroup()

	def set_busy(self, state=True):

		"""
		Show/ hide the busy notification

		Keywords arguments:
		state -- indicates the busy status (default=True)
		"""

		if state:
			self.set_status(_("Busy ..."), status="busy")
		else:
			self.set_status(_("Done!"))
		QtGui.QApplication.processEvents()

	def set_style(self):

		"""Appply the application style"""

		if cfg.style in QtGui.QStyleFactory.keys():
			self.setStyle(QtGui.QStyleFactory.create(cfg.style))
			debug.msg("using style '%s'" % cfg.style)
		else:
			debug.msg("ignoring unknown style '%s'" % cfg.style)
			config.set_config('style', '')

	def set_auto_response(self):

		"""Set the auto response based on the menu action"""

		self.experiment.auto_response = \
			self.ui.action_enable_auto_response.isChecked()
		self.update_preferences_tab()

	def open_autosave_folder(self):

		"""Browse the autosave folder in a platform specific way"""

		if os.name == "nt":
			os.startfile(self.autosave_folder)
		elif os.name == "posix":
			pid = subprocess.Popen(["xdg-open", self.autosave_folder]).pid

	def start_autosave_timer(self):

		"""If autosave is enabled, construct and start the autosave timer"""

		if config.get_config('autosave_interval') > 0:
			debug.msg("autosave interval = %d ms" % config.get_config( \
				'autosave_interval'))
			self.autosave_timer = QtCore.QTimer()
			self.autosave_timer.setInterval(config.get_config( \
				'autosave_interval'))
			self.autosave_timer.setSingleShot(True)
			self.autosave_timer.timeout.connect(self.autosave)
			self.autosave_timer.start()
		else:
			debug.msg("autosave disabled")
			self.autosave_timer = None

	def autosave(self):

		"""Autosave the experiment if there are unsaved changes"""

		if not self.unsaved_changes:
			self.set_status(u'No unsaved changes, skipping backup')
			autosave_path = u''
		else:
			_current_path = self.current_path
			_experiment_path = self.experiment.experiment_path
			_unsaved_changes = self.unsaved_changes
			_window_msg = self.window_msg
			self.current_path = os.path.join(self.autosave_folder, \
				u'%s.opensesame.tar.gz'% unicode(time.ctime()).replace(':', \
				'_'))
			debug.msg("saving backup as %s" % self.current_path)
			try:
				self.save_file(False, remember=False, catch=False)
				self.set_status(_('Backup saved as %s') % self.current_path)
			except:
				self.set_status(_('Failed to save backup ...'))
			autosave_path = self.current_path
			self.current_path = _current_path
			self.experiment.experiment_path = _experiment_path
			self.set_unsaved(_unsaved_changes)
			self.window_message(_window_msg)
		self.start_autosave_timer()
		return autosave_path

	def clean_autosave(self):

		"""Remove old files from the back-up folder"""

		for path in os.listdir(self.autosave_folder):
			_path = os.path.join(self.autosave_folder, path)
			t = os.path.getctime(_path)
			age = (time.time() - t)/(60*60*24)
			if age > config.get_config('autosave_max_age'):
				debug.msg("removing '%s'" % path)
				try:
					os.remove(_path)
				except:
					debug.msg("failed to remove '%s'" \
						% path)

	def save_unsaved_changes(self):

		"""
		If there are unsaved changes, present a dialog and save the changes if
		requested
		"""

		if not self.unsaved_changes:
			return True
		resp = QtGui.QMessageBox.question(self.ui.centralwidget, \
			_("Save changes?"), \
			_("Your experiment contains unsaved changes. Do you want to save your experiment?"), \
			QtGui.QMessageBox.Yes, QtGui.QMessageBox.No, \
				QtGui.QMessageBox.Cancel)
		if resp == QtGui.QMessageBox.Cancel:
			return False
		if resp == QtGui.QMessageBox.Yes:
			self.save_file()
		return True

	def set_unsaved(self, unsaved_changes=True):

		"""
		Set the unsaved changes status

		Keyword arguments:
		unsaved_changes -- a boolean indicating if there are unsaved changes
						   (default=True)
		"""

		self.unsaved_changes = unsaved_changes
		self.window_message()
		debug.msg("unsaved = %s" % unsaved_changes)

	def set_status(self, msg, timeout=5000, status="ready"):

		"""
		Print a text message to the statusbar

		Arguments:
		msg -- a string with the message

		Keyword arguments:
		timeout -- a value in milliseconds after which the message is removed
				   (default=5000)
		"""

		self.ui.statusbar.set_status(msg, timeout=timeout, status=status)

	def window_message(self, msg = None):

		"""
		Display a message in the window border, including an unsaved message indicator

		Keyword arguments:
		msg -- an optional message, if the message should be changed (default = None)
		"""

		if msg != None:
			self.window_msg = msg
		if self.unsaved_changes:
			self.setWindowTitle(_("%s [unsaved]") % self.window_msg)
		else:
			self.setWindowTitle("%s" % self.window_msg)

	def set_immediate_rename(self):

		"""Set the immediate rename option based on the menu action"""

		config.set_config('immediate_rename', \
			self.ui.action_immediate_rename.isChecked())
		debug.msg("set to %s" % config.get_config('immediate_rename'))

	def update_dialog(self, message):

		"""
		Presents an update dialog

		Arguments:
		message -- the message to be displayed
		"""

		from libqtopensesame.ui import update_dialog_ui

		a = QtGui.QDialog(self)
		a.ui = update_dialog_ui.Ui_update_dialog()
		a.ui.setupUi(a)
		self.theme.apply_theme(a)
		a.ui.checkbox_auto_check_update.setChecked(config.get_config( \
			'auto_update_check'))
		a.ui.textedit_notification.setHtml(message)
		a.adjustSize()
		a.exec_()
		config.set_config('auto_update_check', \
			a.ui.checkbox_auto_check_update.isChecked())
		self.update_preferences_tab()

	def check_update(self, dummy=None, always=True):

		"""
		Contacts www.cogsci.nl to check for the most recent version

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler
		always -- a boolean indicating if a dialog should be shown
				  regardless of the auto check update setting and the
				  outcome of the update check
		"""

		import urllib

		if not always and not config.get_config('auto_update_check'):
			debug.msg("skipping update check")
			return

		debug.msg("opening %s" % config.get_config("version_check_url"))

		try:
			fd = urllib.urlopen(config.get_config("version_check_url"))
			mrv = float(fd.read().strip())
		except Exception as e:
			if always:
				self.update_dialog( \
					_("... and is sorry to say that the attempt to check for updates has failed. Please make sure that you are connected to the internet and try again later. If this problem persists, please visit <a href='http://www.cogsci.nl/opensesame'>http://www.cogsci.nl/opensesame</a> for more information."))
			return
		
		# The most recent version as downloaded is always a float. Therefore, we
		# must convert the various possible version numbers to analogous floats.
		# We do this by dividing each subversion number by 100. The only
		# exception is that prereleases should be counted as older than stable
		# releases, so for pre-release we substract one bugfix version.
		# 0.27			->	0.27.0.0			->	0.27
		# 0.27.1 		-> 	0.27.1.0			->	0.2701
		# 0.27~pre1		->	0.27.0.1 - .0001	-> 	0.269901
		# 0.27.1~pre1	->	0.27.1.1 - .0001	-> 	0.270001		
		v = self.version	
		l = v.split("~pre")
		if len(l) == 2:
			lastSubVer = l[1]
			v = l[0]		
			ver = -.0001
		else:
			lastSubVer = 0
			ver = .0
		lvl = 0
		fct = .01
		for subVer in v.split('.') + [lastSubVer]:
			try:
				_subVer = int(subVer)
			except:
				debug.msg('Failed to process version segment %s' % subVer, \
					reason='warning')
				return
			ver += fct**lvl * _subVer
			lvl += 1			
		debug.msg('identifying as version %s' % ver)
		debug.msg('latest stable version is %s' % mrv)
		if mrv > ver:
			self.update_dialog( \
				_("... and is happy to report that a new version of OpenSesame (%s) is available at <a href='http://www.cogsci.nl/opensesame'>http://www.cogsci.nl/opensesame</a>!") % mrv)
		else:
			if always:
				self.update_dialog( \
					_(" ... and is happy to report that you are running the most recent version of OpenSesame."))

	def update_preferences_tab(self):

		"""
		If the preferences tab is open, make sure that its controls are updated
		to match potential changes to the preferences
		"""

		w = self.ui.tabwidget.get_widget('__preferences__')
		if w != None:
			w.set_controls()

	def show_text_in_toolbar(self):

		"""
		Set the toolbar style (text/ icons only) based on the menu action status
		"""

		if self.ui.action_show_text_in_toolbar.isChecked():
			style = QtCore.Qt.ToolButtonTextUnderIcon
		else:
			style = QtCore.Qt.ToolButtonIconOnly
		self.ui.toolbar_main.setToolButtonStyle(style)

	def toggle_overview(self, dummy=None):

		"""
		Set the visibility of the overview area based on the state of the
		toolbar action

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler (default=None)
		"""

		if not self.ui.action_show_overview.isChecked():
			self.ui.dock_overview.setVisible(False)
			return
		self.ui.dock_overview.setVisible(True)

	def refresh_plugins(self, dummy=None):

		"""
		Populate the menu with plug-in entries

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler
		"""

		self.populate_plugin_menu(self.ui.menu_items)

	def refresh_stdout(self, dummy=None):

		"""
		Set the visibility of the debug window (stdout) based on
		the menu action status

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler (default=None)
		"""

		if not self.ui.action_show_stdout.isChecked():
			self.ui.dock_stdout.setVisible(False)
			return
		self.ui.dock_stdout.setVisible(True)

	def refresh_pool(self, make_visible=None):

		"""
		Refresh the file pool

		Keyword arguments:
		make_visible -- an optional boolean that sets the visibility of the file
						pool (default = None)
		"""

		if make_visible != None:
			self.ui.action_show_pool.setChecked(make_visible)
		if not self.ui.action_show_pool.isChecked():
			self.ui.dock_pool.setVisible(False)
			return
		self.ui.dock_pool.setVisible(True)
		self.ui.pool_widget.refresh()

	def refresh_variable_inspector(self, dummy=None):

		"""
		Refresh the variable inspector and sets the visibility based on the menu
		action status

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler
		"""

		if self.ui.action_show_variable_inspector.isChecked():
			self.ui.dock_variable_inspector.setVisible(True)
			self.ui.table_variables.refresh()
		else:
			self.ui.dock_variable_inspector.setVisible(False)

	def restart(self):

		"""Saves the experiment and restarts opensesame"""

		resp = QtGui.QMessageBox.question(self.ui.centralwidget, \
			_("Restart?"), \
			_("A restart is required. Do you want to save the current experiment and restart OpenSesame?"), \
			QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		if resp == QtGui.QMessageBox.No:
			return

		self.save_file()

		# A horrifying hack to make sure that the proper command the restart opensesame is executed
		cmd = []

		# Under Windows, find the path to the Python intepreter and
		# prepend it
		if sys.argv[0] == "opensesame" and os.name == "nt":
			py_exe = "python.exe"
			for d in sys.path:
				py_exe = os.path.join(d, "python.exe")
				if os.path.exists(py_exe):
					break
			debug.msg("located python.exe as '%s'" % py_exe)
			cmd.append(py_exe)

		if sys.argv[0] == "opensesame" and os.name != "nt":
			cmd.append("python")

		cmd.append(sys.argv[0])
		cmd.append(self.current_path)
		if debug.enabled:
			cmd.append("--debug")

		debug.msg("restarting with command '%s'" % cmd)

		libopensesame.experiment.clean_up(debug.enabled)
		self.save_state()
		subprocess.Popen(cmd)
		QtCore.QCoreApplication.quit()

	def closeEvent(self, e):

		"""
		Process a closeEvent, which occurs when the window managers close button
		is clicked

		Arguments:
		e -- the closeEvent or a bool
		"""

		if debug.enabled or self.devmode:
			libopensesame.experiment.clean_up(debug.enabled)
			self.save_state()
			if isinstance(e, bool):
				QtCore.QCoreApplication.quit()
			else:
				e.accept()
			return

		resp = QtGui.QMessageBox.question(self.ui.centralwidget, _("Quit?"), \
			_("Are you sure you want to quit OpenSesame?"), \
			QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		if resp == QtGui.QMessageBox.No:
			if not isinstance(e, bool):
				e.ignore()
		else:
			libopensesame.experiment.clean_up(debug.enabled)
			self.save_unsaved_changes()
			self.save_state()
			if isinstance(e, bool):
				QtCore.QCoreApplication.quit()
			else:
				e.accept()

	def update_recent_files(self):

		"""Recreate the list with recent documents"""

		from libqtopensesame.actions import recent_action

		# Add the current path to the front of the list
		if self.current_path != None and os.path.exists(self.current_path):
			if self.current_path in self.recent_files:
				self.recent_files.remove(self.current_path)
			self.recent_files.insert(0, self.current_path)

		# Trim the list
		self.recent_files = self.recent_files[:5]

		# Build the menu
		self.ui.menu_recent_files.clear()
		if len(self.recent_files) == 0:
			a = QtGui.QAction(_("(No recent files)"), self.ui.menu_recent_files)
			a.setDisabled(True)
			self.ui.menu_recent_files.addAction(a)
		else:
			for path in self.recent_files:
				self.ui.menu_recent_files.addAction( \
					recent_action.recent_action(path, self, \
					self.ui.menu_recent_files))

	def new_file(self):

		"""Discard the current experiment and start with a new file"""

		self.ui.tabwidget.open_start_new()

	def open_file(self, dummy=None, path=None, add_to_recent=True):

		"""
		Open a .opensesame or .opensesame.tar.gz file

		Keyword arguments:
		dummy -- An unused argument which is passed by the signal (default=None)
		path -- The path to the file. If None, a file dialog is presented
				(default=None)
		"""

		if not self.save_unsaved_changes():
			self.ui.tabwidget.open_general()
			return

		if path == None:
			path = QtGui.QFileDialog.getOpenFileName(self.ui.centralwidget, \
				_("Open file"), filter=self.file_type_filter, directory= \
				cfg.file_dialog_path)
		if path == None or path == "":
			return

		path = unicode(path)
		self.set_status("Opening ...")
		self.ui.tabwidget.close_all()
		cfg.file_dialog_path = os.path.dirname(path)

		try:
			exp = experiment.experiment(self, "Experiment", path)
		except Exception as e:
			self.experiment.notify( \
				_("<b>Error:</b> Failed to open '%s'<br /><b>Description:</b> %s<br /><br />Make sure that the file is in .opensesame or .opensesame.tar.gz format. If you should be able to open this file, but can't, please go to http://www.cogsci.nl/opensesame to find out how to recover your experiment and file a bug report.") \
				% (path, e))
			self.print_debug_window(e)
			return

		self.experiment = exp
		self.refresh()
		self.ui.tabwidget.open_general()
		self.set_status("Opened %s" % path)

		if add_to_recent:
			self.current_path = path
			self.window_message(self.current_path)
			self.update_recent_files()
			config.set_config('default_logfile_folder', os.path.dirname( \
				self.current_path))
		else:
			self.window_message("New experiment")
			self.current_path = None

		self.set_auto_response()
		self.set_unsaved(False)

	def save_file(self, dummy=None, remember=True, catch=True):

		"""
		Save the current experiment

		Keyword arguments:
		dummy -- a dummy argument passed by the signal handler (default=None)
		remember -- a boolean indicating whether the file should be included in
					the list of recent files (default=True)
		catch -- a boolean indicating whether exceptions should be caught and
				 displayed in a notification (default=True)
		"""

		if self.current_path == None:
			self.save_file_as()
			return

		# Indicate that we're busy
		self.set_busy(True)
		QtGui.QApplication.processEvents()

		# Get ready, generate the script and see if the script can be
		# re-parsed. In debug mode any errors are not caught. Otherwise. a
		# neat exception is thrown.
		if debug.enabled:
			self.get_ready()
			script = self.experiment.to_string()
			experiment.experiment(self, "Experiment", script)
		else:
			try:
				self.get_ready()
				script = self.experiment.to_string()
				experiment.experiment(self, "Experiment", script)
			except libopensesame.exceptions.script_error as e:
				if not catch:
					raise e
				self.experiment.notify( \
					_("Could not save file, because the script could not be generated. The following error occured:<br/>%s") \
					% e)
				self.set_busy(False)
				return

		# Try to save the experiment if it doesn't exist already
		if debug.enabled:
			resp = self.experiment.save(self.current_path, overwrite=True)
			self.set_status(_("Saved as %s") % self.current_path)
		else:
			try:
				resp = self.experiment.save(self.current_path, overwrite=True)
				self.set_status(_("Saved as %s") % self.current_path)
			except Exception as e:
				if not catch:
					raise e
				self.experiment.notify(_("Failed to save file. Error: %s") % e)
				self.set_busy(False)
				return

		if remember:
			self.update_recent_files()
		self.set_unsaved(False)
		self.window_message(self.current_path)
		self.set_busy(False)

	def save_file_as(self):

		"""Save the current experiment after asking for a file name"""

		if self.current_path == None:
			cfg.file_dialog_path = os.path.join(self.home_folder, \
				self.experiment.sanitize(self.experiment.title, strict=True, \
				allow_vars=False))
		else:
			cfg.file_dialog_path = self.current_path
		path, file_type = QtGui.QFileDialog.getSaveFileNameAndFilter( \
			self.ui.centralwidget, _(u'Save file as ...'), directory= \
			cfg.file_dialog_path, filter=self.file_type_filter)

		if path != None and path != "":
			path = unicode(path)
			cfg.file_dialog_path = os.path.dirname(path)

			# If the extension has not been explicitly typed in, set it based
			# on the selected filter and, if no filter has been set, based on
			# whether there is content in the file pool
			if path[-18:].lower() != u".opensesame.tar.gz" and \
				path[-11:].lower() != u".opensesame":
				debug.msg(u"automagically determing file type")
				if u"(*.opensesame)" in file_type:
					path += u".opensesame"
				elif u"(*.opensesame.tar.gz)" in file_type:
					path += u".opensesame.tar.gz"
				elif len(os.listdir(self.experiment.pool_folder)) == 0:
					path += u".opensesame"
				else:
					path += u".opensesame.tar.gz"
				debug.msg(path)

			self.current_path = path
			self.save_file()

	def close_item_tab(self, item, close_edit=True, close_script=True):

		"""
		Close all tabs that edit and/ or script tabs of a specific item

		Arguments:
		item -- the name of the item

		Keyword arguments:
		close_edit -- a boolean indicating whether the edit tab should be closed
					  (default=True)
		close_script -- a boolean indicating whether the script tab should be
						closed (default=True)
		"""

		debug.msg("closing tabs for '%s'" % item)

		# There's a kind of double loop, because the indices change
		# after a deletion
		redo = True
		while redo:
			redo = False
			for i in range(self.ui.tabwidget.count()):
				w = self.ui.tabwidget.widget(i)
				if close_edit and hasattr(w, "edit_item") and \
					w.edit_item == item:
					self.ui.tabWidget.removeTab(i)
					redo = True
					break
				if close_script and hasattr(w, "script_item") and \
					w.script_item == item:
					self.ui.tabWidget.removeTab(i)
					redo = True
					break

	def update_resolution(self, width, height):

		"""
		Updates the resolution in a way that preserves display centering. This
		is kind of a quick hack. First generate the script, change the
		resolution in the script and then re-parse the script.

		Arguments:
		width -- the display width in pixels
		height -- the display height in pixels
		"""

		debug.msg("changing resolution to %d x %d" % (width, height))

		try:
			script = self.experiment.to_string()
		except libopensesame.exception.script_error as error:
			self.experiment.notify( \
				_("Failed to change the display resolution:") % error)
			return

		script = script.replace("\nset height \"%s\"\n" % \
			self.experiment.get("height"), "\nset height \"%s\"\n" % height)
		script = script.replace("\nset width \"%s\"\n" % \
			self.experiment.get("width"), "\nset width \"%s\"\n" % width)

		try:
			tmp = experiment.experiment(self, self.experiment.title, script, \
				self.experiment.pool_folder)
		except libopensesame.exceptions.script_error as error:
			self.experiment.notify(_("Could not parse script: %s") % error)
			self.edit_script.edit.setText(self.experiment.to_string())
			return

		self.experiment = tmp
		self.refresh()

	def build_item_list(self, name=None):

		"""
		Refreshes the item list

		Keyword arguments:
		name -- a name of the item that has called the build (default=None)
		"""

		debug.msg(name)
		self.experiment.build_item_tree()

	def select_item(self, name):

		"""
		Selects an item from the itemlist and opens the corresponding edit tab

		Arguments:
		name -- the name of the item
		"""

		debug.msg(name)
		if name in self.experiment.unused_items:
			self.experiment.unused_widget.setExpanded(True)
		for item in self.ui.itemtree.findItems(name, \
			QtCore.Qt.MatchFlags(QtCore.Qt.MatchRecursive)):
			self.ui.itemtree.setCurrentItem(item)
		if name in self.experiment.items:
			self.experiment.items[name].open_edit_tab()

	def open_item(self, widget, dummy=None):

		"""
		Open a tab belonging to a widget in the item tree

		Arguments:
		widget -- a QTreeWidgetItem

		Keyword arguments:
		dummy -- an unused parameter which is passed on automatically by the
				 signaller
		"""

		if widget.name == "__general__":
			self.ui.tabwidget.open_general()
		elif widget.name == "__unused__":
			self.ui.tabwidget.open_unused()
		else:
			self.experiment.items[widget.name].open_tab()

	def copy_to_pool(self, fname):

		"""
		Copy a file to the file pool

		Arguments:
		fname -- full path to file
		"""

		import shutil

		renamed = False
		_fname = os.path.basename(fname)
		while os.path.exists(os.path.join(self.experiment.pool_folder, _fname)):
			_fname = "_" + _fname
			renamed = True

		if renamed:
			QtGui.QMessageBox.information(self.ui.centralwidget, \
				_("File renamed"), \
				_("The file has been renamed to '%s', because the file pool already contains a file named '%s'.") \
				% (_fname, os.path.basename(fname)))

		shutil.copyfile(fname, os.path.join(self.experiment.pool_folder, _fname))
		self.refresh_pool(True)

	def get_ready(self):

		"""Give all items the opportunity to get ready for running or saving"""

		# Redo the get_ready loop until no items report having done
		# anything
		debug.msg()
		redo = True
		done = []
		while redo:
			redo = False
			for item in self.experiment.items:
				if item not in done:
					done.append(item)
					if self.experiment.items[item].get_ready():
						debug.msg("'%s' did something" % item)
						redo = True
						break
						
	def print_debug_window(self, msg):
		
		"""
		Prints a message to the debug window.
		
		Arguments:
		msg		--	An object to print to the debug window. If it's an exception
					than a full traceback will be printed.
		"""
		
		from libqtopensesame.widgets import pyterm				
		out = pyterm.output_buffer(self.ui.edit_stdout)
		if isinstance(msg, Exception):
			# The traceback may contain special characters, so it needs to
			# be properly decoded. For some reason, it appears to encoded with
			# the filesystem encoding, at least on Windows 7.
			tb = traceback.format_exc(msg).decode(misc.filesystem_encoding(), \
				errors=u'ignore')
			for s in tb.split(u'\n'):
				out.write(misc.strip_html(s))
		else:
			out.write(self.experiment.unistr(msg))

	
	def experiment_finished(self, exp):

		"""
		Presents a dialog informing the user that the experiment is finished and
		ask if the logfile should be copied to the file pool

		Arguments:
		exp -- an instance of libopensesame.experiment.experiment
		"""

		# Report success and copy the logfile to the filepool if necessary
		resp = QtGui.QMessageBox.question(self.ui.centralwidget, \
			_("Finished!"), \
			_("The experiment is finished and data has been logged to '%s'. Do you want to copy the logfile to the file pool?") \
			% exp.logfile, QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
		if resp == QtGui.QMessageBox.Yes:
			self.copy_to_pool(exp.logfile)
			

	def run_experiment(self, dummy=None, fullscreen=True, quick=False):

		"""
		Runs the current experiment.

		Keyword arguments:
		dummy 		--	A dummy argument that is passed by signaler.
						(default=None)
		fullscreen	--	A boolean to indicate whether the window should be
						fullscreen. (default=True)
		quick		--	A boolean to indicate whether default should be used for
						the log-file and subject number. Mostly useful while
						testing the experiment. (default=False)
		"""

		import openexp.exceptions
		from libqtopensesame.widgets import pyterm
		
		# Disable the entire Window, so that we can't interact with OpenSesame.
		# TODO: This should be more elegant, so that we selectively disable
		# parts of the GUI.
		self.setDisabled(True)

		# Before we run the experiment, we parse it in three steps
		# 1) Apply any pending changes
		# 2) Convert the experiment to a string
		# 3) Parse the string into a new experiment (with all the GUI stuff
		#    stripped off)
		try:
			self.get_ready()
			script = self.experiment.to_string()
			exp = libopensesame.experiment.experiment("Experiment", script, \
				self.experiment.pool_folder)
			exp.experiment_path = self.experiment.experiment_path
		except libopensesame.exceptions.script_error as e:
			self.experiment.notify(unicode(e))
			self.setDisabled(False)
			return

		if quick:
			exp.set("subject_nr", 999)
			exp.set("subject_parity", "odd")
			logfile = os.path.join(config.get_config('default_logfile_folder'), \
				config.get_config('quick_run_logfile'))

		else:

			# Get the participant number
			subject_nr, ok = QtGui.QInputDialog.getInt(self.ui.centralwidget, \
				_("Subject number"), _("Please enter the subject number"), \
				min=0)
			if not ok:
				self.setDisabled(False)
				return

			# Set the subject nr and parity
			exp.set_subject(subject_nr)

			# Suggested filename
			suggested_path = os.path.join(config.get_config( \
				'default_logfile_folder'), u'subject-%d.csv' % subject_nr)

			# Get the data file
			csv_filter = u'Comma-separated values (*.csv)'
			logfile = unicode(QtGui.QFileDialog.getSaveFileName( \
				self.ui.centralwidget, \
				_("Choose location for logfile (press 'escape' for default location)"), \
				suggested_path, filter=csv_filter))

			if logfile == '':
				try:
					# Sometimes this fails, e.g. if the default folder is "/"
					logfile = os.path.join(config.get_config( \
						'default_logfile_folder'), u'defaultlog.csv')
				except:
					logfile = os.path.join(self.home_folder, u'defaultlog.csv')
			else:
				if os.path.splitext(logfile)[1].lower() not in (".csv", \
					".txt", ".dat", ".log"):
					logfile += ".csv"

		# Check if the logfile is writable
		try:
			open(logfile, "w")
		except:
			self.experiment.notify( \
				_("The logfile '%s' is not writable. Please choose another location for the logfile.") \
				% logfile)
			return

		# Remember the location of the logfile
		config.set_config('default_logfile_folder', os.path.split(logfile)[0])

		# Set fullscreen/ window mode
		exp.fullscreen = fullscreen
		exp.logfile = logfile

		# Suspend autosave
		if self.autosave_timer != None:
			debug.msg("stopping autosave timer")
			self.autosave_timer.stop()

		exp.auto_response = self.experiment.auto_response

		# Reroute the standard output to the debug window
		buf = pyterm.output_buffer(self.ui.edit_stdout)
		sys.stdout = buf
		
		if config.get_config(u"runner") == u'multiprocess':			
			from libopensesame.runner import multiprocess_runner as runner								
		elif config.get_config(u"runner") == u'inprocess':
			from libopensesame.runner import inprocess_runner as runner
		elif config.get_config(u"runner") == u'external':
			from libopensesame.runner import external_runner as runner
			
		exception = runner(self, exp).execute()
		if exception != None:
			# Exceptions from other processes will arrive as a tuple
			# Because the tracebacks have to be passed along with them.
			
			if type(exception) == tuple:
				e = exception[0]	#Exception object
				tb = exception[1]	 #Traceback
			
				if isinstance(e, libopensesame.exceptions.runtime_error):
					self.experiment.notify(e)
					#self.print_debug_window(tb)
				elif isinstance(e, openexp.exceptions.openexp_error):					
					self.experiment.notify( \
						_(u"<b>Error</b>: OpenExp error<br /><b>Description</b>: %s") \
						% e)
					#self.print_debug_window(tb)
				else:
					self.experiment.notify( \
						_(u"An unexpected error occurred, which was not caught by OpenSesame. This should not happen! Message:<br/><b>%s</b>") \
						% self.experiment.unistr(e))
					self.print_debug_window(tb)
			else:
				# In case the exception originated from the current process (or opensesamerun)
												
				# Make sure that the experiment cleans up, even though it crashed
				try:
					exp.end()
				except Exception as _e:
					debug.msg("exception: %s" % _e)

				# Report the error
				if isinstance(exception, libopensesame.exceptions.runtime_error):
					self.experiment.notify(exception)
					#self.print_debug_window(exception)
				elif isinstance(exception, openexp.exceptions.openexp_error):					
					self.experiment.notify( \
						_("<b>Error</b>: OpenExp error<br /><b>Description</b>: %s") \
						% exception)
					#self.print_debug_window(exception)
				else:
					self.experiment.notify( \
						_("An unexpected error occurred, which was not caught by OpenSesame. This should not happen! Message:<br/><b>%s</b>") \
						% self.experiment.unistr(exception))
					self.print_debug_window(exception)
		else:
			self.experiment_finished(exp)
									
		# Undo the standard output rerouting
		sys.stdout = sys.__stdout__
		self.ui.edit_stdout.show_prompt()

		# Resume autosave, but not if opensesamerun is called
		if self.autosave_timer != None:
			debug.msg("resuming autosave timer")
			self.autosave_timer.start()
		
		# Re-enable the GUI.
		self.setDisabled(False)			
		
	def run_experiment_in_window(self):

		"""Runs the experiment in a window"""

		self.run_experiment(fullscreen=False)

	def run_quick(self):

		"""Run the experiment without asking for subject nr and logfile"""

		self.run_experiment(fullscreen=False, quick=True)

	def refresh(self, changed_item=None, refresh_edit=True, \
		refresh_script=True):

		"""
		Refreshes all parts of the interface that may have changed because of a
		changed item

		Keyword arguments:
		changed_item -- the name of a specific item that should be refreshed
						(default = None)
		refresh_edit -- a boolean to indicate if the edit tabs should be
						refreshed (default = True)
		refresh_script -- a boolean to indicate if the script tabs should be
						  refreshed (default = True)
		"""

		# Make sure the refresh does not get caught in
		# a recursive loop
		if self.lock_refresh:
			return
		self.lock_refresh = True

		self.set_busy(True)
		debug.msg(changed_item)

		index = self.ui.tabwidget.currentIndex()
		for i in range(self.ui.tabwidget.count()):
			w = self.ui.tabwidget.widget(i)
			if hasattr(w, "__general_tab__"):
				w.refresh()
			# For now the unused tab doesn't need to be refreshed
			if hasattr(w, "__unused_tab__"):
				pass
			if refresh_edit and hasattr(w, "__edit_item__") and (changed_item \
				== None or w.__edit_item__ == changed_item):
				if w.__edit_item__ in self.experiment.items:
					self.experiment.items[w.__edit_item__].edit_widget()
			if refresh_script and hasattr(w, "__script_item__") and ( \
				changed_item == None or w.__script_item__ == changed_item):
				if w.__script_item__ in self.experiment.items:
					self.experiment.items[w.__script_item__].script_widget()

		self.ui.tabwidget.setCurrentIndex(index)
		self.build_item_list()
		self.refresh_variable_inspector()
		self.refresh_pool()
		self.lock_refresh = False
		self.set_busy(False)

	def hard_refresh(self, changed_item):

		"""
		Closes and reopens the tabs for a changed item. This is different from
		the normal refresh in the sense that here the tabs are reinitialized
		from scratch which is necessary if a new instance of the item has been
		created.

		Arguments:
		changed_item -- the name of the changed item
		"""

		# Make sure the refresh does not get caught in
		# a recursive loop
		if self.lock_refresh:
			return
		self.lock_refresh = True

		self.set_busy(True)
		debug.msg(changed_item)
		index = self.ui.tabwidget.currentIndex()

		for i in range(self.ui.tabwidget.count()):
				w = self.ui.tabwidget.widget(i)
				if hasattr(w, "edit_item") and (changed_item == None or \
					w.edit_item == changed_item) and w.edit_item in \
					self.experiment.items:
					debug.msg("reopening edit tab %s" % changed_item)
					self.ui.tabwidget.removeTab(i)
					self.experiment.items[w.edit_item].open_edit_tab(i, False)
					w = self.ui.tabwidget.widget(i)
					w.edit_item = changed_item
				if hasattr(w, "script_item") and (changed_item == None or \
					w.script_item == changed_item) and w.script_item in \
					self.experiment.items:
					debug.msg("reopening script tab %s" % changed_item)
					self.ui.tabwidget.removeTab(i)
					self.experiment.items[w.script_item].open_script_tab(i, False)
					w = self.ui.tabwidget.widget(i)
					w.script_item = changed_item

		self.ui.tabwidget.setCurrentIndex(index)
		self.lock_refresh = False
		self.set_busy(False)

	def populate_plugin_menu(self, menu):

		"""
		Adds a list of plugins to a menu

		Arguments:
		menu -- a QMenu instance
		"""

		from libqtopensesame.actions import plugin_action

		cat_menu = {}
		for plugin in libopensesame.plugins.list_plugins():
			debug.msg("found plugin '%s'" % plugin)
			cat = libopensesame.plugins.plugin_category(plugin)
			if cat not in cat_menu:
				cat_menu[cat] = QtGui.QMenu(cat)
				cat_menu[cat] = menu.addMenu(self.experiment.icon("plugin"), \
					cat)
			cat_menu[cat].addAction(plugin_action.plugin_action(self, \
				cat_menu[cat], plugin))

	def add_item(self, item_type, refresh=True, name=None, interactive=True):

		"""
		Adds a new item to the item list

		Arguments:
		item_type -- the type of the item to add

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		name -- a custom name to give the item (default=None)
		interactive -- indicates whether the GUI is allowed to be interactive.
					   More specifically, this means that the GUI can ask for
					   a new name, if the immediate rename option is enabled.
					   (default=True)

		Returns:
		The name of the new item
		"""

		# Get a unique name if none has been specified
		name = self.experiment.unique_name("%s" % item_type)

		debug.msg("adding %s (%s)" % (name, item_type))

		# If the item type is a plugin, we need to use the plugin mechanism
		if libopensesame.plugins.is_plugin(item_type):

			# In debug mode, exceptions are not caught
			if debug.enabled:
				item = libopensesame.plugins.load_plugin(item_type, name, \
					self.experiment, None, self.experiment.item_prefix())
			else:
				try:
					item = libopensesame.plugins.load_plugin(item_type, name, \
						self.experiment, None, self.experiment.item_prefix())
				except Exception as e:
					self.experiment.notify( \
						_("Failed to load plugin '%s'. Error: %s") \
						% (item_type, e))
					return

		else:
			# Load a core item
			exec("from libqtopensesame.items import %s" % item_type)
			name = self.experiment.unique_name("%s" % item_type)
			item = eval("%s.%s(name, self.experiment)" % (item_type, item_type))

		# Optionally, ask for a new name right away
		if interactive and config.get_config('immediate_rename'):
			while True:
				name, ok = QtGui.QInputDialog.getText(self, _("New name"), \
					_("Please enter a name for the new %s") % item_type, \
					text=name)
				name = self.experiment.sanitize(unicode(name), strict=True, \
					allow_vars=False)
				if name not in self.experiment.items:
					break
			if not ok:
				return None
			name = unicode(name)
			item.name = name

		# Add the item to the item list
		self.experiment.items[name] = item
		self.set_unsaved()

		# Optionally, refresh the interface
		if refresh:
			debug.msg("refresh")
			self.refresh()
			self.select_item(name)

		return name

	def add_loop(self, refresh=True, parent=None):

		"""
		Add a loop item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new loop (default=None)

		Returns:
		The name of the new loop
		"""

		from libqtopensesame.dialogs import new_loop_sequence_dialog

		d = new_loop_sequence_dialog.new_loop_sequence_dialog(self, \
			self.experiment, "loop", parent)
		d.exec_()
		if d.action == "cancel":
			return None
		loop = self.add_item("loop", False)
		if d.action == "new":
			item_name = self.add_item(d.item_type, False)
			self.experiment.items[loop].set("item", item_name)
		else:
			self.experiment.items[loop].set("item", d.item_name)
		if refresh:
			self.refresh()
			self.select_item(loop)
		return loop

	def add_sequence(self, refresh=True, parent=None):

		"""
		Add a sequence item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new sequence (default=None)

		Returns:
		The name of the new sequence
		"""

		from libqtopensesame.dialogs import new_loop_sequence_dialog

		d = new_loop_sequence_dialog.new_loop_sequence_dialog(self, \
			self.experiment, "sequence", parent)
		d.exec_()
		if d.action == "cancel":
			return None
		seq = self.add_item("sequence", False)
		if d.action == "new":
			item_name = self.add_item(d.item_type, False)
			self.experiment.items[seq].items.append((item_name, "always"))
		else:
			self.experiment.items[seq].items.append((d.item_name, "always"))
		if refresh:
			self.refresh()
			self.select_item(seq)

		return seq

	def add_sketchpad(self, refresh=True, parent=None):

		"""
		Add a sketchpad item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default = None)

		Returns:

		The name of the new item
		"""

		return self.add_item("sketchpad", refresh)

	def add_feedback(self, refresh=True, parent=None):

		"""
		Add a feedback item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""
		return self.add_item("feedback", refresh)

	def add_sampler(self, refresh=True, parent=None):

		"""
		Add a sampler item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("sampler", refresh)

	def add_synth(self, refresh=True, parent=None):

		"""
		Add a synth item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item
				  (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("synth", refresh)

	def add_keyboard_response(self, refresh=True, parent=None):

		"""
		Add a keyboard_response item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("keyboard_response", refresh)

	def add_mouse_response(self, refresh=True, parent=None):

		"""
		Add a mouse_response item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("mouse_response", refresh)

	def add_logger(self, refresh=True, parent=None):

		"""
		Add a logger item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("logger", refresh)

	def add_inline_script(self, refresh=True, parent=None):

		"""
		Add an inline_script item and ask for an item to fill the loop with

		Keyword arguments:
		refresh -- a bool to indicate if the interface should be refreshed
				   (default=True)
		parent -- the parent item for the new item (default=None)

		Returns:
		The name of the new item
		"""

		return self.add_item("inline_script", refresh)

	def drop_item(self, add_func):

		"""
		Create a new item after an item has been dragged and dropped from the
		toolbar. The necessary information is stored in the itemtree.

		Arguments:
		add_func -- a function to call to create the new item
		"""

		from libqtopensesame.widgets import draggables

		debug.msg(u'dropping from toolbar')

		# Determine the drop target
		if draggables.drop_target == None:
			return
		target, index, select = draggables.drop_target

		# Create a new item and return if it fails
		if not isinstance(add_func, basestring):
			new_item = add_func(False, parent=target)
		else:
			new_item = self.add_item(add_func, False)
		if new_item == None:
			self.refresh(target)
			return

		if target == u'__start__':
			self.experiment.set(u'start', new_item)
		else:
			self.experiment.items[target].items.insert(index, (new_item, \
				u'always'))

		self.refresh(target)
		if select:
			self.select_item(new_item)

	def drag_item(self, add_func):

		"""
		Drag an item from the item toolbar

		Arguments:
		add_func -- a function to create a new item, if the item is dropped
		"""

		from libqtopensesame.widgets import draggables

		debug.msg("dragging")

		# Reset the drop target
		draggables.drop_target = None

		# Start the drop action
		d = QtGui.QDrag(self.ui.centralwidget)
		m = QtCore.QMimeData()
		m.setText("__osnew__ %s" % add_func)
		d.setMimeData(m)

		# Check if the drop was successful
		if d.start(QtCore.Qt.CopyAction) == QtCore.Qt.CopyAction:
			self.drop_item(add_func)
		else:
			# Create a new item
			if type(add_func) != str:
				new_item = add_func(False)
			else:
				new_item = self.add_item(add_func, False)

			if new_item != None:
				debug.msg("adding to unused")
				self.refresh()
				self.select_item(new_item)

	def drag_loop(self):

		"""Drag a new loop"""

		self.drag_item(self.add_loop)

	def drag_sequence(self):

		"""Drag a new sequence"""

		self.drag_item(self.add_sequence)

	def drag_sketchpad(self):

		"""Drag a new sketchpad"""

		self.drag_item(self.add_sketchpad)

	def drag_feedback(self):

		"""Drag a new feedback"""

		self.drag_item(self.add_feedback)

	def drag_sampler(self):

		"""Drag a new sampler"""

		self.drag_item(self.add_sampler)

	def drag_synth(self):

		"""Drag a new synth"""

		self.drag_item(self.add_synth)

	def drag_keyboard_response(self):

		"""Drag a new keyboard_response"""

		self.drag_item(self.add_keyboard_response)

	def drag_mouse_response(self):

		"""Drag a new mouse_response"""

		self.drag_item(self.add_mouse_response)

	def drag_logger(self):

		"""Drag a new logger"""

		self.drag_item(self.add_logger)

	def drag_inline_script(self):

		"""Drag a new inline_script"""

		self.drag_item(self.add_inline_script)

