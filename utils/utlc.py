from __future__ import print_function
import sys
import os, stat
import re
import glob
import subprocess

#
# Console raw keyboard input
#

if os.name == 'nt':
	# Windows
	import msvcrt
else:
	# Posix (Linux, OS X)
	import sys
	import termios
	import atexit
	from select import select

class KeyboardHandler(object):
	def __init__(self):
		if os.name == 'nt':
			pass
		else:
			# Save the terminal settings
			self.fd = sys.stdin.fileno()
			self.new_term = termios.tcgetattr(self.fd)
			self.old_term = termios.tcgetattr(self.fd)
			# New terminal setting unbuffered
			self.new_term[3] = (self.new_term[3] & ~termios.ICANON & ~termios.ECHO)
			termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.new_term)
			# Support normal-terminal reset at exit
			atexit.register(self.set_normal_term)

	def set_normal_term(self):
		if os.name == 'nt':
			pass
		else:
			termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.old_term)

	def getch(self):
		if os.name == 'nt':
			return msvcrt.getch().decode('utf-8')
		else:
			return sys.stdin.read(1)

	def kbhit(self):
		''' Returns True if keyboard character was hit, False otherwise.
		'''
		if os.name == 'nt':
			return msvcrt.kbhit()
		else:
			dr,dw,de = select([sys.stdin], [], [], 0)
			return dr != []

kbd = KeyboardHandler()

#
# Console text coloring and printing
#

try:
	import colorama
	from colorama import Fore, Back, Style
	colorama.init()

	FOREGROUND_BLUE		= Fore.BLUE
	FOREGROUND_GREEN	= Fore.GREEN
	FOREGROUND_RED		= Fore.RED
	BACKGROUND_BLUE		= Back.BLUE
	BACKGROUND_GREEN	= Back.GREEN
	BACKGROUND_RED		= Back.RED
	BACKGROUND_YELLOW	= Back.YELLOW

	# derived colors - combinations of the above flags
	FOREGROUND_INTENSE_CYAN		= Fore.CYAN + Style.BRIGHT
	FOREGROUND_INTENSE_RED		= Fore.RED + Style.BRIGHT
	FOREGROUND_INTENSE_YELLOW	= Fore.YELLOW + Style.BRIGHT
	FOREGROUND_WHITE			= Fore.WHITE + Style.BRIGHT

	RESET_COLORS				= Style.RESET_ALL

	def print_color(print_string, color ):
		print( color + print_string + RESET_COLORS )

except ImportError:
	# Fallback if colorama not available
	FOREGROUND_BLUE		= ""
	FOREGROUND_GREEN	= ""
	FOREGROUND_RED		= ""
	BACKGROUND_BLUE		= ""
	BACKGROUND_GREEN	= ""
	BACKGROUND_RED		= ""
	BACKGROUND_YELLOW	= ""

	FOREGROUND_INTENSE_CYAN		= ""
	FOREGROUND_INTENSE_RED		= ""
	FOREGROUND_INTENSE_YELLOW	= ""
	FOREGROUND_WHITE			= ""

	RESET_COLORS				= ""

	def print_color(print_string, color ):
		print( print_string )

#
# ANSI escape code printfs
#

# invert
def print_I( print_string ):
    print( "\033[7m" + print_string + "\033[0m" )	# black on white/inverse

#
# Time
#

# duration in seconds, return elapsed time in hh:mm:ss
def GetElapsedTime( duration ):
	e = int(duration )
	elapsedTime = '{:02d}:{:02d}:{:02d}'.format(e // 3600, (e % 3600 // 60), e % 60)
	return elapsedTime

#
# Environment
#

VALVE_NO_AUTO_P4 = '0'
bRestoreEnv = False

# save local env
def SaveEnv():
	global VALVE_NO_AUTO_P4, bRestoreEnv
	# save VALVE_NO_AUTO_P4 environment var
	VALVE_NO_AUTO_P4 = os.getenv("VALVE_NO_AUTO_P4", "0" )
	# set to 1 for our script (we need this to batch p4 commands/run much faster in
	# environs where this is 1)
	os.environ['VALVE_NO_AUTO_P4'] = '1'
	# Path to bin/win64 from game/csgo/import_scripts
	# import_scripts is at: game/csgo/import_scripts
	# bin/win64 is at: game/bin/win64
	# So we need: ../../bin/win64 (up 2 levels from import_scripts, then into bin/win64)
	newPath = os.path.abspath("../../bin/win64/")
	print(f"[DEBUG] Current directory: {os.getcwd()}")
	print(f"[DEBUG] Adding to PATH: {newPath}")
	
	# Check if source1import.exe exists
	source1import_path = os.path.join(newPath, "source1import.exe")
	if os.path.exists(source1import_path):
		print(f"[DEBUG] ✓ Found source1import.exe at: {source1import_path}")
	else:
		print(f"[DEBUG] ✗ WARNING: source1import.exe NOT FOUND at: {source1import_path}")
		print(f"[DEBUG] Trying to list directory contents...")
		try:
			if os.path.exists(newPath):
				files = os.listdir(newPath)
				print(f"[DEBUG] Directory exists, contains {len(files)} files")
				if 'source1import.exe' in files:
					print(f"[DEBUG] source1import.exe IS in the directory list!")
			else:
				print(f"[DEBUG] Directory does not exist: {newPath}")
		except Exception as e:
			print(f"[DEBUG] Error listing directory: {e}")
	
	if newPath not in os.environ['PATH']:
		os.environ['PATH']+=f";{newPath}"
		print(f"[DEBUG] PATH updated successfully")
	else:
		print(f"[DEBUG] Path already in PATH")
	bRestoreEnv = True

# restore local env
def RestoreEnv():
	global VALVE_NO_AUTO_P4, bRestoreEnv
	if ( bRestoreEnv ):
		os.environ['VALVE_NO_AUTO_P4'] = VALVE_NO_AUTO_P4
		newPath = os.path.abspath("../../../game/bin/win64/")
		if newPath in os.environ['PATH']:
			os.environ['PATH']=os.environ['PATH'].replace(f";{newPath}", "")

#
# Misc
#

def Error(str):
	RestoreEnv()
	print( "\033[1;31m" + str + "\n\033[0m" )
	sys.exit(1)

# read text file, //comments, and blank lines are stripped
def ReadTextFile(fname):
	fr = open(fname, "r")
	refs = fr.readlines()
	refs = [x.strip() for x in refs]
	refs = [x for x in refs if x]
	refs = [x for x in refs if (x.startswith("//") == False) ]
	fr.close()
	return refs

def ReadTextFileNoStrip(fname):
	fr = open(fname, "r")
	refs = fr.readlines()
	fr.close()
	return refs

def RunCommand(cmd, errorCallback = None):
	print_I( "--------------------------------" )
	print_I( "- Running Command: " + cmd )
	print_I( "--------------------------------" )

	try:
		subprocess.check_call( cmd , shell=True )
	except subprocess.CalledProcessError as e:
		if errorCallback is not None:
			errorCallback(cmd)
		else:
			Error ( "Error running:\n>>>%s\nAborting" % cmd )

def EnsureFileWritable( fname ):
	if ( os.path.exists( fname ) ):
		os.chmod( fname, stat.S_IWRITE )

#
# List Manipulation
#

def RefsStringFromList(lst):
	lst = [x.strip() for x in lst]
	lst = [x.replace("\"", "") for x in lst]
	refs = "importfilelist\n{\n"
	for line in lst:
		if len(line):
			refs += "\t\"file\"" + " \"" + line + "\"\n"
	refs += "}\n"
	return refs

def ListStringFromRefs(refs):
	refs = [x.replace("\"", "") for x in refs]
	refs = [x.strip() for x in refs]

	expecting = ["importfilelist", "{", "file", "}", "Done"]
	idx = 0

	lst = ""

	for line in refs:
		if len(line):

			if ( expecting[idx] == "Done"):
				break

			if ( line.startswith("//") or line.startswith("#") ) :
				continue

			if ( expecting[idx] == "file" ):

				if ( line.startswith("file") ):
					fname = line[4:].strip()
					lst += fname + "\n"
				else:
					if ( line.startswith("}")):
						break
					else:
						Error("Error Expecting: \"file\" <filename> or }")
				continue

			if ( line != expecting[idx]) :
				Error("Expecting " + expecting[idx])
			else:
				idx += 1

	return lst

def SplitMdlFromRefs(mdls, others, refs):
	tempStr = ListStringFromRefs(refs)
	temp = tempStr.split("\n")

	for line in temp:
		if line.endswith(".mdl"):
			mdls.append(line)
		else:
			others.append(line)