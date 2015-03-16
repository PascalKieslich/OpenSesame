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

from libopensesame.var_store import var_store
from libopensesame.item_store import item_store
from libopensesame.file_pool_store import file_pool_store
from libopensesame.python_workspace import python_workspace
from libopensesame.exceptions import osexception
from libopensesame import misc, item, debug
from libopensesame.py3compat import *
import os.path
import shutil
import time
import tarfile
import tempfile
import codecs
import warnings

class experiment(item.item):

	"""
	desc: |
		The `experiment` object controls the flow of the experiment. If you are
		writing Python inline code, there are a few functions in the experiment
		object that may be useful, mostly to `get` and `set` variables, and to
		retrieve files from the file pool. The `experiment` object is a property
		of the `inline_script` object, so you can access it as `self.experiment`
		in an inline_script. For convenience, you can also refer to it simply as
		`exp`. For example, the following script retrieves the full path to a
		file from the pool, shows it using a canvas, and stores the timestamp of
		the display presentation as `canvas_timestamp`, so it can be logged:

		__Example:__

		~~~ {.python}
		from openexp.canvas import canvas
		my_canvas = canvas(exp)
		my_canvas.image(exp.get_file('my_image.png'))
		timestamp = my_canvas.show()
		exp.set('canvas_timestamp', timestamp)
		~~~

		__Function list:__

		%--
		toc:
			mindepth: 2
			maxdepth: 2
		--%
	"""

	def __init__(self, name=u'experiment', string=None, pool_folder=None,
		experiment_path=None, fullscreen=False, auto_response=False,
		logfile=u'defaultlog.csv', subject_nr=0, items=None, workspace=None,
		resources={}):

		"""
		desc:
			Constructor. The experiment is created automatically be OpenSesame
			and you will generally not need to create it yourself.

		keywords:
			name:
				desc:	The name of the experiment.
				type:	[str, unicode]
			string:
				desc:	A string containing the experiment definition, the
						name of an OpenSesame experiment file, or `None` to
						create a blank experiment.
				type:	[str, unicode, NoneType]
			pool_folder:
				desc:	A specific folder to be used for the file pool, or
						`None` to use a new temporary folder.
				type:	[str, unicode, NoneType]
			experiment_path:
				desc:	The path of the experiment file. This will need to
						be specified even if a filename was passed using the
						`string` keyword.
				type:	[str, unicode, NoneType]
			fullscreen:
				desc:	Indicates whether the experiment should be executed in
						fullscreen.
				type:	bool
			auto_response:
				desc:	Indicates whether auto-response mode should be enabled.
				type:	bool
			logfile:
				desc:	The logfile path.
				type:	[unicode, str]
			subject_nr:
				desc:	The subject number.
				type:	int
			items:
				desc:	An `item_store` object to be used for storing items
						internally, or `None` to create a new item store.
				type:	[item_store, NoneType]
			workspace:
				desc:	A `python_workspace` object to be used for executing
						custom Python code, or `None` to create a new workspace.
				type:	[python_workspace, NoneType]
			resources:
				desc:	A dictionary with names as keys and paths as values.
						This serves as a look-up table for resources.
				type:	dict
		"""

		self.var = var_store(self)
		self.pool = file_pool_store(self, folder=pool_folder)
		if items is None:
			self.items = item_store(self)
		else:
			self.items = items
		if workspace is None:
			self.python_workspace = python_workspace(self)
		else:
			self.python_workspace = workspace
		self.running = False
		self.auto_response = auto_response
		self.plugin_folder = u'plugins'
		self.start_response_interval = None
		self.cleanup_functions = []
		self.restart = False
		self.resources = resources

		# Set default variables
		self.var.start = u'experiment'
		self.var.title = u'My Experiment'
		self.var.transparent_variables = u'no'
		self.var.bidi = u'no'
		self.var.round_decimals = 2

		# Sound parameters
		self.var.sound_freq = 48000
		self.var.sound_sample_size = -16 # Negative values mean signed
		self.var.sound_channels = 2
		self.var.sound_buf_size = 1024

		# Backend parameters
		self.var.canvas_backend = u'xpyriment'
		self.var.keyboard_backend = u'legacy'
		self.var.mouse_backend = u'xpyriment'
		self.var.sampler_backend = u'legacy'
		self.var.synth_backend = u'legacy'

		# Display parameters
		self.var.width = 1024
		self.var.height = 768
		self.var.background = u'black'
		self.var.foreground = u'white'
		if fullscreen is not None:
			if fullscreen:
				self.var.fullscreen = u'yes'
			else:
				self.var.fullscreen = u'no'

		# Font parameters
		self.var.font_size = 18
		self.var.font_family = u'mono'
		self.var.font_italic = u'no'
		self.var.font_bold = u'no'
		self.var.font_underline = u'no'

		# Logfile parameters
		self._log = None
		self.logfile = logfile

		# This is some duplication of the option parser in qtopensesame,
		# but nevertheless keep it so we don't need qtopensesame
		self.debug = debug.enabled

		string = self.open(string)
		item.item.__init__(self, name, self, string)

		# Default subject info
		self.set_subject(subject_nr)
		# Restore experiment path
		if experiment_path is not None:
			self.experiment_path = experiment_path

	@property
	def pool_folder(self):

		"""Deprecated."""

		warnings.warn(
			u'experiment.pool_folder is deprecated. Use file_pool_store instead.',
			DeprecationWarning)
		return self.pool.folder()

	@property
	def fallback_pool_folder(self):

		"""Deprecated."""

		warnings.warn(
			u'experiment.fallback_pool_folder is deprecated. Use file_pool_store instead.',
			DeprecationWarning)
		return self.pool.fallback_folder()

	def get_file(self, path):

		"""Deprecated."""

		warnings.warn(
			u'experiment.get_file() is deprecated. Use file_pool_store instead.',
			DeprecationWarning)
		return self.pool[path]

	def file_in_pool(self, path):

		"""Deprecated."""

		warnings.warn(
			u'experiment.file_in_pool() is deprecated. Use file_pool_store instead.',
			DeprecationWarning)
		return path in self.pool

	def module_container(self):

		"""Specify the module that contains the item modules"""

		return u'libopensesame'

	def item_prefix(self):

		"""
		A prefix for the plug-in classes, so that [prefix][plugin] class is used
		instead of the [plugin] class.
		"""

		return u''

	def set_subject(self, nr):

		"""
		desc:
			Sets the subject number and parity (even/ odd). This function is
			called automatically when an experiment is started, so you do not
			generally need to call it yourself.

		arguments:
			nr:
				desc:	The subject nr.
				type:	int

		example: |
			exp.set_subject(1)
			print('Subject nr = %d' % exp.get('subject_nr'))
			print('Subject parity = %s' % exp.get('subject_parity'))
		"""

		# Set the subject nr and parity
		self.var.subject_nr = nr
		if nr % 2 == 0:
			self.var.subject_parity = u'even'
		else:
			self.var.subject_parity = u'odd'

	def read_definition(self, s):

		"""
		Extracts a the definition of a single item from the string.

		Arguments:
		s	--	The definition string.

		Returns:
		A (str, str) tuple with the full string minus the definition string
		and the definition string.
		"""

		# Read the string until the end of the definition
		def_str = u''
		line = next(s, None)
		if line is None:
			return None, u''
		get_next = False
		while True:
			if len(line) > 0:
				if line[0] != u'\t':
					break
				else:
					def_str += line + u'\n'
			line = next(s, None)
			if line is None:
				break
		return line, def_str

	def from_string(self, string):

		"""
		Reads the entire experiment from a string.

		Arguments:
		string	--	The definition string.
		"""

		debug.msg(u"building experiment")
		s = iter(string.split("\n"));
		line = next(s, None)
		while line is not None:
			get_next = True
			try:
				l = self.split(line)
			except ValueError as e:
				raise osexception( \
					u"Failed to parse script. Maybe it contains illegal characters or unclosed quotes?", \
					exception=e)
			if len(l) > 0:
				self.parse_variable(line)
				# Parse definitions
				if l[0] == u"define":
					if len(l) != 3:
						raise osexception( \
							u'Failed to parse definition', line=line)
					item_type = l[1]
					item_name = self.sanitize(l[2])
					line, def_str = self.read_definition(s)
					get_next = False
					self.items.new(item_type, item_name, def_str)
			# Advance to next line
			if get_next:
				line = next(s, None)

	def run(self):

		"""Runs the experiment."""

		# Save the date and time, and the version of OpenSesame
		self.var.datetime = safe_decode(time.strftime(u'%c'), enc=self.encoding,
			errors=u'ignore')
		self.var.opensesame_version = misc.version
		self.var.opensesame_codename = misc.codename

		self.save_state()
		self.running = True
		self.init_display()
		self.init_sound()
		self.init_log()
		self.reset_feedback()

		print(u"experiment.run(): experiment started at %s" % time.ctime())

		if self.var.start in self.items:
			self.items[self.start].prepare()
			self.items[self.start].run()
		else:
			raise osexception( \
				"Could not find item '%s', which is the entry point of the experiment" \
				% self.start)

		print(u"experiment.run(): experiment finished at %s" % time.ctime())

		self.end()

	def pause(self):

		"""
		desc:
			Pauses the experiment, sends the Python workspace to the GUI, and
			waits for the GUI to send a resume signal. This requires an output
			channel.
		"""

		from openexp.canvas import canvas
		from openexp.keyboard import keyboard
		import pickle
		if not hasattr(self, u'output_channel'):
			debug.msg(u'Cannot pause, because there is no output channel.')
			return
		d = self.python_workspace._globals.copy()
		for key, value in d.items():
			try:
				pickle.dumps(value)
			except:
				del d[key]
		d[u'__pause__'] = True
		self.output_channel.put(d)
		pause_canvas = canvas(self)
		pause_canvas.text(
			u'The experiment has been paused.<br />Press spacebar to resume...')
		pause_keyboard = keyboard(self, keylist=[u'space'])
		pause_canvas.show()
		try:
			pause_keyboard.get_key()
		finally:
			self.output_channel.put({'__pause__' : False})

	def cleanup(self):

		"""Calls all the cleanup functions."""

		while len(self.cleanup_functions) > 0:
			func = self.cleanup_functions.pop()
			debug.msg(u"calling cleanup function")
			func()

	def end(self):

		"""Nicely ends the experiment."""

		from openexp import sampler, canvas
		self.running = False
		try:
			self._log.flush()
			os.fsync(self._log)
			self._log.close()
		except:
			pass
		sampler.close_sound(self)
		canvas.close_display(self)
		self.cleanup()
		self.restore_state()

	def to_string(self):

		"""
		Encodes the experiment into a string.

		Returns:
		A Unicode definition string for the experiment.
		"""

		s = u'# Generated by OpenSesame %s (%s)\n' % (misc.version, \
			misc.codename) + \
			u'# %s (%s)\n' % (time.ctime(), os.name) + \
			u'# <http://www.cogsci.nl/opensesame>\n\n'
		for var in self.var:
			s += self.variable_to_string(var)
		s += u'\n'
		for item in sorted(self.items):
			s += self.items[item].to_string() + u'\n'
		return s

	def resource(self, name):

		"""
		Retrieves a file from the resources folder.

		Arguments:
		name	--	The file name.

		Returns:
		A Unicode string with the full path to the file in the resources
		folder.
		"""

		name = self.unistr(name)
		if self is not None:
			if name in self.resources:
				return self.resources[name]
			if os.path.exists(self.get_file(name)):
				return self.get_file(name)
		path = misc.resource(name)
		if path is None:
			raise Exception( \
				u"The resource '%s' could not be found in libopensesame.experiment.resource()" \
				% name)
		return path

	def save(self, path, overwrite=False, update_path=True):

		"""
		desc:
			Saves the experiment to file. If no extension is provided,
			.opensesame.tar.gz is chosen by default.

		arguments:
			path:
				desc:	The target file to save to.
				type:	[str, unicode]

		keywords:
			overwrite:
				desc:	Indicates if existing files should be overwritten.
				type:	bool
			update_path:
				desc:	Indicates if the experiment_path attribute should be
						updated.
				type:	bool

		returns:
			desc:	The path on successful saving or False otherwise.
			type:	[unicode, bool]
		"""

		path = safe_decode(path, enc=self.encoding)
		debug.msg(u'asked to save "%s"' % path)
		# Determine the extension
		ext = os.path.splitext(path)[1].lower()
		# If the extension is .opensesame, save the script as plain text
		if ext == u'.opensesame':
			if os.path.exists(path) and not overwrite:
				return False
			debug.msg(u'saving as .opensesame file')
			f = open(path, u'w')
			f.write(self.usanitize(self.to_string()))
			f.close()
			self.experiment_path = os.path.dirname(path)
			return path
		# Use the .opensesame.tar.gz extension by default
		if path[-len(u'.opensesame.tar.gz'):] != u'.opensesame.tar.gz':
			path += u'.opensesame.tar.gz'
		if os.path.exists(path) and not overwrite:
			return False
		debug.msg(u"saving as .opensesame.tar.gz file")
		# Write the script to a text file
		script = self.to_string()
		script_path = os.path.join(self.pool_folder, u'script.opensesame')
		f = open(script_path, u"w")
		f.write(self.usanitize(script))
		f.close()
		# Create the archive in a a temporary folder and move it afterwards.
		# This hack is needed, because tarfile fails on a Unicode path.
		tmp_path = tempfile.mktemp(suffix=u'.opensesame.tar.gz')
		tar = tarfile.open(tmp_path, u'w:gz')
		tar.add(script_path, u'script.opensesame')
		os.remove(script_path)
		# We also create a temporary pool folder, where all the filenames are
		# Unicode sanitized to ASCII format. Again, this is necessary to deal
		# with poor Unicode support in .tar.gz.
		tmp_pool = tempfile.mkdtemp(suffix=u'.opensesame.pool')
		for fname in os.listdir(self.pool_folder):
			sname = self.usanitize(fname)
			shutil.copyfile(os.path.join(self.pool_folder, fname),
				os.path.join(tmp_pool, sname))
		tar.add(tmp_pool, u'pool', True)
		tar.close()
		# Move the file to the intended location
		shutil.move(tmp_path, path)
		if update_path:
			self.experiment_path = os.path.dirname(path)
		# Clean up the temporary pool folder
		try:
			shutil.rmtree(tmp_pool)
			debug.msg(u'Removed temporary pool folder: %s' % tmp_pool)
		except:
			debug.msg(u'Failed to remove temporary pool folder: %s' % tmp_pool)
		return path

	def open(self, src):

		"""
		If the path exists, open the file, extract the pool and return the
		contents of the script.opensesame. Otherwise just return the input
		string, because it probably was a definition to begin with.

		Arguments:
		src		--	A definition string or a file to be opened.

		Returns:
		A unicode defition string.
		"""

		# If the path is not a path at all, but a string containing
		# the script, return it. Also, convert the path back to Unicode before
		# returning.
		if not os.path.exists(src):
			debug.msg(u'opening from unicode string')
			self.experiment_path = None
			return safe_decode(src, enc=self.encoding, errors=u'replace')
		# If the file is a regular text script,
		# read it and return it
		ext = u'.opensesame.tar.gz'
		if src[-len(ext):] != ext:
			debug.msg(u'opening .opensesame file')
			self.experiment_path = os.path.dirname(src)
			return self.unsanitize(open(src, u'rU').read())
		debug.msg(u"opening .opensesame.tar.gz file")
		# If the file is a .tar.gz archive, extract the pool to the pool folder
		# and return the contents of opensesame.script.
		tar = tarfile.open(src, u'r:gz')
		for name in tar.getnames():
			# Here, all paths except name are Unicode. In addition, fname is
			# Unicode unsanitized, because the files as saved are Unicode
			# sanitized (see save()).
			uname = safe_decode(name, enc=self.encoding)
			folder, fname = os.path.split(uname)
			fname = self.unsanitize(fname)
			if folder == u"pool":
				debug.msg(u"extracting '%s'" % uname)
				if py3:
					tar.extract(name, self.pool_folder)
				else:
					tar.extract(name, safe_encode(self.pool_folder,
						enc=misc.filesystem_encoding()))
				os.rename(os.path.join(self.pool_folder, uname), \
					os.path.join(self.pool_folder, fname))
				os.rmdir(os.path.join(self.pool_folder, folder))
		script_path = os.path.join(self.pool_folder, u"script.opensesame")
		tar.extract(u"script.opensesame", self.pool_folder)
		script = self.unsanitize(open(script_path, u"rU").read())
		os.remove(script_path)
		self.experiment_path = os.path.dirname(src)
		return script

	def reset_feedback(self):

		"""Resets the feedback variables (acc, avg_rt, etc.)."""

		self.var.total_responses = 0
		self.var.total_correct = 0
		self.var.total_response_time = 0
		self.var.avg_rt = u"undefined"
		self.var.average_response_time = u"undefined"
		self.var.accuracy = u"undefined"
		self.var.acc = u"undefined"

	def var_info(self):

		"""
		Returns a list of (name, value) tuples with variable descriptions
		for the main experiment.

		Returns:
		A list of tuples.
		"""

		l = []
		for var in self.var:
			l.append( (var, self.var.get(var)) )
		return l

	def var_list(self, filt=u''):

		"""
		Returns a list of (name, value, description) tuples with variable
		descriptions for all items

		Keyword arguments:
		filt	--	A search string to filter by. (default=u'')

		Returns:
		A list of tupless
		"""

		l = []
		# Create a dictionary of items that also includes the experiment
		item_dict = dict(list(self.items.items()) + [(u'global', self)]).items()
		seen = []
		for item_name, item in item_dict:
			# Create a dictionary of variables that includes the broadcasted
			# ones as wel as the indirectly registered ones (using item.set())
			var_dict = item.var_info() + item.var.items()
			for var, val in var_dict:
				if var not in seen and (filt in var.lower() or filt in \
					self.unistr(val).lower() or filt in item_name.lower()):
					l.append( (var, val, item_name) )
					seen.append(var)
		return l

	def init_sound(self):

		"""Intializes the sound backend."""

		from openexp import sampler
		sampler.init_sound(self)

	def init_display(self):

		"""Initializes the canvas backend."""

		from openexp import canvas
		canvas.init_display(self)
		self.python_workspace[u'win'] = self.window

	def init_log(self):

		"""Opens the logile."""

		# Do not open the logfile if it's already open
		if self._log is not None:
			return
		# If only a filename is present, we interpret this filename as relative
		# to the experiment folder, instead of relative to the current working
		# directory.
		if os.path.basename(self.logfile) == self.logfile and \
			self.experiment_path is not None:
			self.logfile = os.path.join(self.experiment_path, self.logfile)
		# Open the logfile
		self._log = codecs.open(self.logfile, u'w', encoding=self.encoding)
		debug._print(u"experiment.init_log(): using '%s' as logfile (%s)" % \
			(self.logfile, self.encoding))

	def save_state(self):

		"""
		Saves the system state so that it can be restored after the experiment.
		"""

		from libopensesame import inline_script
		inline_script.save_state()

	def restore_state(self):

		"""Restores the system to the state as saved by save_state()."""

		from libopensesame import inline_script
		inline_script.restore_state()

	def _sleep_func(self, ms):

		"""
		Sleeps for a specific time.

		* This is a stub that should be replaced by a proper function by the
		  canvas backend. See openexp._canvas.legacy.init_display()

		Arguments:
		ms	--	The sleep duration.
		"""

		raise osexception( \
			u"experiment._sleep_func(): This function should be set by the canvas backend.")

	def _time_func(self):

		"""
		Gets the time.

		* This is a stub that should be replaced by a proper function by the
		  canvas backend. See openexp._canvas.legacy.init_display()

		Returns:
		A timestamp in milliseconds. Depending on the backend, this may be an
		int or a float.
		"""

		raise osexception( \
			u"experiment._time_func(): This function should be set by the canvas backend.")

def clean_up(verbose=False, keep=[]):

	warnings.warn(u'libopensesame.experiment.clean_up() is deprecated' % var,
		DeprecationWarning)
