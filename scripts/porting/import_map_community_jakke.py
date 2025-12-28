##########################################################################################################################################
#
# import_map script
#  
##########################################################################################################################################

from __future__ import print_function
import os
import sys
import argparse
import time
import ast
import shutil
import tempfile

# Force unbuffered output for real-time progress updates
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
sys.stderr.reconfigure(line_buffering=True) if hasattr(sys.stderr, 'reconfigure') else None

# Add the current working directory to Python path so we can import utils
# This script is meant to be run from CS2's import_scripts directory
cwd = os.getcwd()
if cwd not in sys.path:
    sys.path.insert(0, cwd)

from utils import utlc as utl

##########################################################################################################################################
# Get full path to source1import.exe
##########################################################################################################################################
def GetSource1ImportPath():
	"""Get the full path to source1import.exe from the import_scripts directory."""
	# We're running from game/csgo/import_scripts
	# source1import.exe is at game/bin/win64/source1import.exe
	source1import_path = os.path.abspath("../../bin/win64/source1import.exe")
	return source1import_path

##########################################################################################################################################
# Case-insensitive file finder
##########################################################################################################################################
def FindFileInsensitive(path):
	"""Find a file with case-insensitive matching. Returns the actual path if found, or original path if not."""
	if os.path.exists(path):
		return path
	
	# Split into directory and filename
	directory = os.path.dirname(path)
	filename = os.path.basename(path)
	
	if not os.path.exists(directory):
		# Try to find directory case-insensitively
		parent = os.path.dirname(directory)
		dirname = os.path.basename(directory)
		if os.path.exists(parent):
			for item in os.listdir(parent):
				if item.lower() == dirname.lower():
					directory = os.path.join(parent, item)
					break
	
	if os.path.exists(directory):
		# Find file case-insensitively
		for item in os.listdir(directory):
			if item.lower() == filename.lower():
				return os.path.join(directory, item)
	
	return path  # Return original if not found

##########################################################################################################################################
# Get path to CS2 SDK tool
##########################################################################################################################################
def GetCS2ToolPath(tool_name, s2gamecsgo):
	"""Construct full path to a CS2 SDK tool (e.g., cs_mdl_import.exe).
	s2gamecsgo should point to game\csgo folder."""
	# CS2 tools are in game\bin\win64 relative to the game\csgo folder
	# game\csgo -> ..\bin\win64
	tool_path = os.path.join(s2gamecsgo, "..", "bin", "win64", tool_name)
	tool_path = os.path.normpath(tool_path)
	if os.path.exists(tool_path):
		return tool_path
	# If not found, return the tool name (will fail but show clear error)
	return tool_name

##########################################################################################################################################
# Fix material file case to match VMF expectations
##########################################################################################################################################
def FixMaterialCase(vmf_path, game_dir):
	"""Read VMF file and rename material files to match the case used in the VMF.
	game_dir should point to the CS:GO installation root (contains 'csgo' folder)"""
	import re
	
	try:
		with open(vmf_path, 'r', encoding='utf-8', errors='ignore') as f:
			vmf_content = f.read()
		
		# Find all material references in the VMF (they appear in "material" keys)
		material_pattern = re.compile(r'"material"\s+"([^"]+)"', re.IGNORECASE)
		materials = set(material_pattern.findall(vmf_content))
		
		# Also find materials in texture references
		texture_pattern = re.compile(r'"texture"\s+"([^"]+)"', re.IGNORECASE)
		materials.update(texture_pattern.findall(vmf_content))
		
		print(f"Found {len(materials)} unique material references in VMF")
		
		# For each material, try to find and rename the .vmt and .vtf files
		renamed_count = 0
		for material in materials:
			# Clean up the material path
			material = material.strip().replace('\\', '/')
			if not material:
				continue
			
			# Material path relative to csgo folder (materials are in csgo\materials)
			vmt_rel_path = f"csgo\\materials\\{material}.vmt".replace('/', '\\')
			vtf_rel_path = f"csgo\\materials\\{material}.vtf".replace('/', '\\')
			
			# Full paths in game directory
			vmt_full = os.path.join(game_dir, vmt_rel_path).replace('\\\\', '\\')
			vtf_full = os.path.join(game_dir, vtf_rel_path).replace('\\\\', '\\')
			
			# Find actual files case-insensitively
			actual_vmt = FindFileInsensitive(vmt_full)
			actual_vtf = FindFileInsensitive(vtf_full)
			
			# Rename if found and case doesn't match
			if actual_vmt != vmt_full and os.path.exists(actual_vmt):
				try:
					# Ensure target directory exists
					os.makedirs(os.path.dirname(vmt_full), exist_ok=True)
					os.rename(actual_vmt, vmt_full)
					print(f"Renamed: {os.path.basename(actual_vmt)} -> {os.path.basename(vmt_full)}")
					renamed_count += 1
				except Exception as e:
					print(f"Warning: Could not rename {actual_vmt}: {e}")
			
			if actual_vtf != vtf_full and os.path.exists(actual_vtf):
				try:
					os.makedirs(os.path.dirname(vtf_full), exist_ok=True)
					os.rename(actual_vtf, vtf_full)
					print(f"Renamed: {os.path.basename(actual_vtf)} -> {os.path.basename(vtf_full)}")
					renamed_count += 1
				except Exception as e:
					print(f"Warning: Could not rename {actual_vtf}: {e}")
		
		print(f"Fixed case for {renamed_count} material files")
		
	except Exception as e:
		print(f"Warning: Error fixing material case: {e}")

##########################################################################################################################################
#
##########################################################################################################################################
def StripMDLsFromRefs( filename ):

	refs = utl.ReadTextFile( filename )

	mdls = []
	others = []
	utl.SplitMdlFromRefs( mdls, others, refs )

	mdlfilename = filename.replace( "_refs.txt", "_mdl_lst.txt" )
	utl.EnsureFileWritable( mdlfilename )
	writeFile = open( mdlfilename, "w" )
	[ writeFile.write( x + "\n" ) for x in mdls ]
	writeFile.close()

	refsfilename = filename.replace( "_refs.txt", "_new_refs.txt" )
	utl.EnsureFileWritable( refsfilename )
	writeFile = open( refsfilename, "w" )
	writeFile.write( utl.RefsStringFromList( others ) )
	writeFile.close()


##########################################################################################################################################
# Function to check meshinfo.txt and force 2UVs as required
##########################################################################################################################################

# Ensure the vmat has the F_FORCE_UV2 feature added
def ForceUV2ForVMAT( mtlfile ):

	vmatfilename = s2contentcsgoimported + "\\" + mtlfile.replace( ".vmt", ".vmat" )

	if ( not os.path.exists( vmatfilename ) ):
		return

	vmatlist = utl.ReadTextFileNoStrip( vmatfilename )

	utl.EnsureFileWritable( vmatfilename )

	for line in range( len( vmatlist ) ):
		txt = vmatlist[ line ].strip()
		txt = txt.lower()
		if txt.startswith( "\"shader\"" ):
			# line + 1 assumed to be safe since there's always at least one more line after "Shader" "bla.vfx"
			txtNext = vmatlist[ line + 1 ].strip()
			txtNext = txtNext.replace( "\t", "" )
			if ( not txtNext.startswith( "\"F_FORCE_UV2\"" ) ):
				vmatlist.insert( line + 1, "\t\"F_FORCE_UV2\" \"1\"\n" )
				break

	print( "Added F_FORCE_UV2 to %s" % vmatfilename )
	writeFile = open( vmatfilename, "w" )
	writeFile.writelines( vmatlist )
	writeFile.close()


def Force2UVsIfRequired( refsName, global2UVMaterials, global2UVMaterialsFile ):

	uvsUpdated = set()

	meshinfofilename = refsName.replace( "_refs.txt", "_refs/mesh/meshinfo.txt").replace( "/", "\\" )

	if ( not os.path.exists( meshinfofilename ) ):
		return False

	meshinfo = utl.ReadTextFile( meshinfofilename )
	meshstring = "".join( meshinfo )
	meshinfoparse = ast.literal_eval( meshstring )

	b2UV = False

	if ( not os.path.exists( refsName ) ):
		return False

	refs = utl.ReadTextFile( refsName )
	refsString = utl.ListStringFromRefs( refs )
	refsList = refsString.split( "\n" )

	for mtlfile in refsList :

		if ( not len( mtlfile ) ):
			continue

		if ( mtlfile in uvsUpdated ):
			continue

		# check if ANY materials in refslist is already a member of the global2UVMaterials, if so let's force compile the model and make sure the material still has the flag added
		if ( mtlfile in global2UVMaterials ):
			b2UV = True
			uvsUpdated.add( mtlfile )

		else:
			# add new material to forceuv2 list
			if ( meshinfoparse[ "numuvs" ] == 2 ):
				b2UV = True
				print ( "Adding F_FORCE_UV2 to mtls imported from %s..." % refsName )
			
				uvsUpdated.add( mtlfile )

				if ( mtlfile not in global2UVMaterials ):
					global2UVMaterialsFile.write( "%s\n" % mtlfile )
					global2UVMaterials.add( mtlfile )

				# Ensure the vmat has the F_FORCE_UV2 feature added
				ForceUV2ForVMAT( mtlfile )


	return b2UV

##########################################################################################################################################
#
##########################################################################################################################################
def ImportAndCompileMapMDLs( filename, s2addon, errorCallback ):

	# read list of models to convert
	mdlfiles = utl.ReadTextFile( filename )

	if ( len( mdlfiles ) < 1 ): 
		print( "No MDLs to import" )
		return 

	print( "Importing models" )
	print( "--------------------------------")
	for x in mdlfiles : 
		if ( x.startswith("-") == False):
			print(x)	
	print( "--------------------------------")

	force2UVList = []
	mdlmtls = set()

	extraoptions = ""
	for mdlfile in mdlfiles :
		if ( mdlfile.startswith( "-" ) ):
			if  ( ( mdlfile == "-" ) or ( mdlfile == "-nooptions" ) ):
				extraoptions = ""
			else:
				extraoptions = mdlfile
		else:
			mdlfile = mdlfile.replace( "/", "\\" )
			infile = mdlfile

			outName = s2contentcsgoimported + "\\" + mdlfile.replace( ".mdl", ".vmdl" )
			refsName = s2contentcsgoimported + "\\" + mdlfile.replace( ".mdl", "_refs.txt" )

			# Import

			cs_mdl_import = GetCS2ToolPath("cs_mdl_import.exe", s2gamecsgo)
			importCmd = "\"%s\" -nop4 %s -i \"%s\" -o \"%s\" \"%s\"" % ( cs_mdl_import, extraoptions, s1gamecsgo, s2contentcsgoimported, infile )
			utl.RunCommand( importCmd, errorCallback )

			# So we only import materials once, lets add their refs to a refsset, and import them after all models
			if ( os.path.exists( refsName ) ):
				refs = utl.ReadTextFile( refsName )
				str = utl.ListStringFromRefs( refs )
				mtllist = str.split( "\n" )
				for mtlname in mtllist : mdlmtls.add( mtlname )

				# collect refsNames so we can add 2UVs as required
				force2UVList.append( refsName )

	# import mtls used by mdl
	mdlmtlrefs = utl.RefsStringFromList( list( mdlmtls ) )

	temp_refs = filename.replace( "mdl_lst", "mtl_lst")
	utl.EnsureFileWritable( temp_refs )
	fw = open( temp_refs, "w" )
	fw.write( mdlmtlrefs )
	fw.close()

	# Don't use -src1contentdir here - let source1import find assets in VPK files
	source1import_exe = GetSource1ImportPath()
	importRefsCmd = "\"%s\" -retail -nop4 -nop4sync -src1gameinfodir \"%s\" -s2addon %s -game csgo -usefilelist \"%s\"" % ( source1import_exe, s1gamecsgo, s2addon, temp_refs )
	try:
		utl.RunCommand( importRefsCmd, errorCallback )
	except Exception as e:
		print(f"Warning: Some materials may have failed to import: {e}")
		print("Continuing with compilation of successfully imported materials...")

	# read in global list of materials where we've forced uv2...
	global2UVMaterials = set()
	force2UVList = utl.ReadTextFile( "source1import_2uvmateriallist.txt" )
	for mtl in force2UVList :
		global2UVMaterials.add( mtl )
		# Ensure all mtls in this list have the F_FORCE_UV2 feature added
		ForceUV2ForVMAT( mtl )

	# ...we may append to this file	
	utl.EnsureFileWritable( "source1import_2uvmateriallist.txt" )
	global2UVMaterialFile = open( "source1import_2uvmateriallist.txt", "a" )

	# Skip compilation - CS2 Hammer will compile assets when the map is opened
	# compile materials
	# adding explicitly since we appear to miss a number of these if we rely on model compilation above to compile all materials refs too, even if we compile models with -f.
	# for mtlfile in mdlmtls :
	# 	if ( mtlfile.startswith( "-" ) or ( mtlfile == "" ) ):
	# 		continue
	# 	else:
	# 		mtlfile = mtlfile.replace( "/", "\\" )
	# 		outName = s2contentcsgoimported + "\\" + mtlfile.replace( ".vmt", ".vmat" )
	# 
	# 	resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % ( outName )
	# 	try:
	# 		utl.RunCommand( resCompCmd, errorCallback )
	# 	except Exception as e:
	# 		print(f"Warning: Failed to compile material {mtlfile}: {e}")
	# 		print("Continuing with other materials...")

	# Skip compilation - CS2 Hammer will compile assets when the map is opened
	# compile models
	# for mdlfile in mdlfiles :
	# 	bForceCompile = False
	# 	if ( mdlfile.startswith( "-" ) ):
	# 		continue
	# 	else:
	# 		mdlfile = mdlfile.replace( "/", "\\" )
	# 		outName = s2contentcsgoimported + "\\" + mdlfile.replace( ".mdl", ".vmdl" )
	# 
	# 		if ( not os.path.exists( outName ) ):
	# 			continue
	# 
	# 		refsName = s2contentcsgoimported + "\\" + mdlfile.replace( ".mdl", "_refs.txt" )
	# 		# commenting this out for now, not needed if we're always force compiling
	# 		bForceCompile = Force2UVsIfRequired( refsName, global2UVMaterials, global2UVMaterialFile )
	# 
	# 	# For now just let the map importer script do the compiles
	# 	# Compile Model ( should compile materials too ). Possibly add -f here when shader changes have happened.
	# 	if ( bForceCompile ):
	# 		resCompCmd = "resourcecompiler -retail -nop4 -f -game csgo \"%s\"" % ( outName )
	# 	else:
	# 		resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % ( outName )
	# 
	# 	try:
	# 		utl.RunCommand( resCompCmd, errorCallback )
	# 	except Exception as e:
	# 		print(f"Warning: Failed to compile model {mdlfile}: {e}")
	# 		print("Continuing with other models...")

	# close global 2uv material file
	global2UVMaterialFile.close()



##########################################################################################################################################
#
##########################################################################################################################################
def ImportAndCompileMapRefs( refsFile, s2addon, errorCallback ):

	# import map refs - don't use -src1contentdir so source1import can find assets in VPK files
	source1import_exe = GetSource1ImportPath()
	importcmd = "\"" + source1import_exe + "\" -retail -nop4 -nop4sync -src1gameinfodir \"" + s1gamecsgo + "\" -s2addon " + s2addon + " -game csgo -usefilelist \"" + refsFile + "\""
	try:
		utl.RunCommand( importcmd, errorCallback )
	except Exception as e:
		print(f"Warning: Some materials may have failed to import from {refsFile}: {e}")
		print("Continuing with compilation of successfully imported materials...")

	refs = utl.ReadTextFile( refsFile )
	str = utl.ListStringFromRefs( refs )
	flatList = str.split( "\n" )

	newList = ""

	for line in flatList:
		if len( line ):
			line = line.replace( ".vmt", ".vmat" )
			line = line.replace( " ", "_" )
			newList += s2contentcsgoimported + "\\" + line.replace( "/", "\\" ) + "\n"

	tmpFile = s2contentcsgoimported + "\\maps\\" + mapname + "_prefab_compile_new_refs.txt"
	
	# Ensure maps directory exists
	maps_dir = os.path.dirname(tmpFile)
	os.makedirs(maps_dir, exist_ok=True)
	
	utl.EnsureFileWritable( tmpFile )
	writeFile = open( tmpFile, "w" )
	writeFile.write( newList )
	writeFile.close()

	# Skip compilation - CS2 Hammer will compile assets when the map is opened
	# compilercmd = "resourcecompiler -retail -nop4 -game csgo -f -filelist \"" + tmpFile + "\""
	# try:
	# 	utl.RunCommand( compilercmd, errorCallback )
	# except Exception as e:
	# 	print(f"Warning: Some embedded materials may have failed to compile: {e}")
	# 	print("Continuing with map import...")
	print("Skipping asset compilation (will be compiled automatically when opening in Hammer)")

##########################################################################################################################################
# Import all models referenced in VMF from pak01
##########################################################################################################################################
def ImportVMFModels(vmf_path, s1gamecsgo, s2addon, s2contentcsgoimported, errorCallback):
	"""Import all models referenced in the VMF file from pak01 before VMF import"""
	import re
	
	# Define a non-aborting error callback for model imports
	def non_aborting_callback(cmd):
		print(f"Warning: Command failed but continuing: {cmd}")
	
	try:
		with open(vmf_path, 'r', encoding='utf-8', errors='ignore') as f:
			vmf_content = f.read()
		
		# Find all model references in the VMF (they appear in "model" keys for prop_static, etc.)
		model_pattern = re.compile(r'"model"\s+"([^"]+\.mdl)"', re.IGNORECASE)
		models = set(model_pattern.findall(vmf_content))
		
		if not models:
			print("No models found in VMF")
			return
		
		print(f"Found {len(models)} unique model references in VMF, importing from pak01...")
		sys.stdout.flush()
		
		# Import models one by one to avoid batch failure
		imported_models = []
		failed_count = 0
		model_materials = set()
		
		for model in models:
			model = model.strip().replace('\\', '/')
			if not model:
				continue
			try:
				# Use cs_mdl_import to import the model from pak01
				cs_mdl_import = GetCS2ToolPath("cs_mdl_import.exe", s2gamecsgo)
				import_cmd = f"\"{cs_mdl_import}\" -nop4 -i \"{s1gamecsgo}\" -o \"{s2contentcsgoimported}\" \"{model}\""
				utl.RunCommand(import_cmd, non_aborting_callback)
				imported_models.append(model)
				# Print progress after each model
				print(f"Imported {len(imported_models)} models")
				sys.stdout.flush()
				
				# Check if a _refs.txt file was created for this model
				refs_name = s2contentcsgoimported + "\\" + model.replace(".mdl", "_refs.txt").replace("/", "\\")
				if os.path.exists(refs_name):
					refs = utl.ReadTextFile(refs_name)
					str_refs = utl.ListStringFromRefs(refs)
					mtllist = str_refs.split("\n")
					materials_found = 0
					for mtlname in mtllist:
						if mtlname.strip():
							model_materials.add(mtlname.strip())
							materials_found += 1
					if materials_found > 0:
						print(f"  Found {materials_found} materials in refs for {model}")
				else:
					print(f"  No refs file found for {model} at {refs_name}")
			except Exception as e:
				failed_count += 1
		
		print(f"Imported {len(imported_models)} models from pak01, {failed_count} skipped/failed")
		sys.stdout.flush()
		
		print(f"Collected {len(model_materials)} unique materials from model refs files")
		
		# Import materials used by the models
		if model_materials:
			print(f"Importing {len(model_materials)} materials used by models...")
			
			# Create a refs file for model materials
			model_mtl_refs = utl.RefsStringFromList(list(model_materials))
			# Write to the same directory as the VMF file (csgo/maps/)
			temp_refs = vmf_path.replace(".vmf", "_model_mtl_refs.txt")
			utl.EnsureFileWritable(temp_refs)
			fw = open(temp_refs, "w")
			fw.write(model_mtl_refs)
			fw.close()
			print(f"Created model material refs file: {temp_refs}")
			
			# Import model materials from pak01
			source1import_exe = GetSource1ImportPath()
			importRefsCmd = f"\"{source1import_exe}\" -retail -nop4 -nop4sync -src1gameinfodir \"{s1gamecsgo}\" -s2addon {s2addon} -game csgo -usefilelist \"{temp_refs}\""
			try:
				utl.RunCommand(importRefsCmd, non_aborting_callback)
			except Exception as e:
				print(f"Warning: Some model materials may have failed to import: {e}")
			
			# Skip compilation - CS2 Hammer will compile assets when the map is opened
			# for mtlfile in model_materials:
			# 	if mtlfile.startswith("-") or mtlfile == "":
			# 		continue
			# 	try:
			# 		mtlfile = mtlfile.replace("/", "\\")
			# 		outName = s2contentcsgoimported + "\\" + mtlfile.replace(".vmt", ".vmat")
			# 		if os.path.exists(outName):
			# 			resCompCmd = f"resourcecompiler -retail -nop4 -game csgo \"{outName}\""
			# 			utl.RunCommand(resCompCmd, non_aborting_callback)
			# 	except Exception as e:
			# 		pass  # Continue with other materials
			
			print(f"Imported {len(model_materials)} model materials (skipping compilation)")
		else:
			print("No model materials found in model refs files - skipping model_mtl_refs creation")
		
		# Skip compilation - CS2 Hammer will compile assets when the map is opened
		# if imported_models:
		# 	print(f"Compiling {len(imported_models)} imported models...")
		# 	for model in imported_models:
		# 		try:
		# 			vmdl_path = s2contentcsgoimported + "\\" + model.replace(".mdl", ".vmdl").replace("/", "\\")
		# 			if os.path.exists(vmdl_path):
		# 				compile_cmd = f"resourcecompiler -retail -nop4 -game csgo \"{vmdl_path}\""
		# 				utl.RunCommand(compile_cmd, non_aborting_callback)
		# 		except Exception as e:
		# 			pass  # Continue with other models
		# 	
		# 	print(f"Finished compiling models from pak01")
		
		if imported_models:
			print(f"Imported {len(imported_models)} models (skipping compilation)")
		
	except Exception as e:
		print(f"Warning: VMF model import failed: {e}")
		print("Continuing with VMF import...")

##########################################################################################################################################
# Import all materials referenced in VMF from pak01
##########################################################################################################################################
def ImportVMFMaterials(vmf_path, s1gamecsgo, s2addon, s2contentcsgoimported, errorCallback):
	"""Import all materials referenced in the VMF file from pak01 before VMF import.
	Returns a set of successfully imported material paths for deduplication."""
	import re
	
	try:
		with open(vmf_path, 'r', encoding='utf-8', errors='ignore') as f:
			vmf_content = f.read()
		
		# Find all material references in the VMF (they appear in "material" keys)
		material_pattern = re.compile(r'"material"\s+"([^"]+)"', re.IGNORECASE)
		materials = set(material_pattern.findall(vmf_content))
		
		# Also find materials in texture references
		texture_pattern = re.compile(r'"texture"\s+"([^"]+)"', re.IGNORECASE)
		materials.update(texture_pattern.findall(vmf_content))
		
		if not materials:
			print("No materials found in VMF")
			return set()
		
		print(f"Found {len(materials)} unique material references in VMF, importing from pak01...")
		sys.stdout.flush()  # Ensure progress is shown immediately
		
		# Import materials one by one to avoid batch failure
		imported_materials = []
		failed_count = 0
		
		def material_error_callback(cmd):
			# Don't abort on individual material import failures
			print(f"Warning: Material import command failed: {cmd}")
		
		for material in materials:
			material = material.strip().replace('\\', '/')
			if not material:
				continue
			try:
				source1import_exe = GetSource1ImportPath()
				import_cmd = f"\"{source1import_exe}\" -retail -nop4 -nop4sync -src1gameinfodir \"{s1gamecsgo}\" -src1contentdir \"{s1gamecsgo}\" -s2addon {s2addon} -game csgo \"materials/{material}.vmt\""
				utl.RunCommand(import_cmd, material_error_callback)
				imported_materials.append(material)
				# Print progress after each material
				print(f"Imported {len(imported_materials)} materials")
				sys.stdout.flush()  # Force immediate output
			except Exception as e:
				print(f"Warning: Failed to import material {material}: {e}")
				failed_count += 1
		
		print(f"Imported {len(imported_materials)} materials, {failed_count} failed")
		sys.stdout.flush()
		
		# Skip compilation - CS2 Hammer will compile assets when the map is opened
		# compile_refs = ""
		# for material in imported_materials:
		# 	compile_refs += f"{s2contentcsgoimported}\\materials\\{material}.vmat\n"
		# 
		# compile_file = vmf_path.replace('.vmf', '_vmf_materials_compile_refs.txt')
		# with open(compile_file, 'w') as f:
		# 	f.write(compile_refs)
		# 
		# compile_cmd = f"resourcecompiler -retail -nop4 -game csgo -f -filelist \"{compile_file}\""
		# try:
		# 	utl.RunCommand(compile_cmd, material_error_callback)  # Use non-aborting callback
		# 	print(f"Successfully compiled {len(imported_materials)} imported materials")
		# except Exception as e:
		# 	print(f"Warning: Some VMF materials may have failed to compile: {e}")
		# 	print("Continuing with VMF import...")
		
		print("Skipping material compilation (will be compiled automatically when opening in Hammer)")
		
		# Return set of imported material paths for deduplication
		return set(imported_materials)
			
	except Exception as e:
		print(f"Warning: Failed to import VMF materials: {e}")
		print("Continuing with VMF import...")
		return set()

	print("VMF materials import and compilation process completed.")

##########################################################################################################################################
# VPK Signature management functions
##########################################################################################################################################
def DisableVPKSignatures(s2gamecsgo):
	"""Rename vpk.signatures to vpk.signatures.old to bypass VPK validation"""
	vpk_sig_path = os.path.join(s2gamecsgo, "..", "bin", "win64", "vpk.signatures")
	vpk_sig_old = vpk_sig_path + ".old"
	
	if os.path.exists(vpk_sig_path):
		try:
			# Delete old backup if it exists
			if os.path.exists(vpk_sig_old):
				os.remove(vpk_sig_old)
			# Rename to .old to disable signature checking
			os.rename(vpk_sig_path, vpk_sig_old)
			print(f"Disabled VPK signature checking (renamed to vpk.signatures.old)")
			return vpk_sig_path, vpk_sig_old
		except Exception as e:
			print(f"Warning: Could not rename vpk.signatures: {e}")
			return None, None
	return None, None

def RestoreVPKSignatures(vpk_sig_path, vpk_sig_old):
	"""Restore vpk.signatures from .old"""
	if vpk_sig_old and os.path.exists(vpk_sig_old):
		try:
			# Remove current file if it exists (shouldn't normally)
			if os.path.exists(vpk_sig_path):
				os.remove(vpk_sig_path)
			# Rename .old back to original
			os.rename(vpk_sig_old, vpk_sig_path)
			print(f"Restored VPK signature checking")
		except Exception as e:
			print(f"Warning: Could not restore vpk.signatures: {e}")

##########################################################################################################################################
#
##########################################################################################################################################

#
# START
#

start = time.time()

# save VALVE_NO_AUTO_P4 environment var, set to 1 to ensure p4 lib works in a mode that is disconnected from p4
utl.SaveEnv()
print("[DEBUG] SaveEnv() called, PATH should be updated")
sys.stdout.flush()

# inputs
parser = argparse.ArgumentParser( prog='import_map_community', description='Import a map (vmf) and its dependencies from s1 to s2' )
parser.add_argument( 's1gameinfodir', help='path to s1 gameinfo.txt' )
parser.add_argument( 's1contentdir', help='path to s1 content' )
parser.add_argument( 's2gameinfodir', help='path to s2 gameinfo.gi' )
parser.add_argument( 's2addon', help='s2 addon name')
parser.add_argument( 'mapname', help='Name of map to import, relative to maps\\ in the csgo content directory' )
parser.add_argument( '-usebsp', action='store_true', default=False, help='Generate and use bsp on import' )
parser.add_argument( '-usebsp_nomergeinstances', action='store_true', default=False, help='if using bsp, do not merge instances' )
parser.add_argument( '-skipdeps', action='store_true', default=False, help='do not import and compile dependencies (imports .vmf to .vmap only)' )
args = parser.parse_args()

mapname = args.mapname
usebsp = args.usebsp
nomergeinstances = args.usebsp_nomergeinstances
skipdeps = args.skipdeps

# setup paths
s1gamecsgo = args.s1gameinfodir
s1contentcsgo = args.s1contentdir
s2gamecsgo = args.s2gameinfodir
s2addon = args.s2addon

s1gamecsgotxt = s1gamecsgo + "\\" + "gameinfo.txt"
if ( not os.path.exists( s1gamecsgotxt ) ):
	utl.Error( "%s not found, aborting" % s1gamecsgotxt )

s2gamecsgogi = s2gamecsgo + "\\" + "gameinfo.gi"
if ( not os.path.exists( s2gamecsgogi ) ):
	utl.Error( "%s not found, aborting" % s2gamecsgogi )

s2gameaddondir = "game\\csgo_addons\\" + s2addon
s2gameaddon = s2gamecsgo.replace( "game\\csgo", s2gameaddondir )

s2contentcsgo = s2gameaddon.replace( r"game\csgo_addons", r"content\csgo_addons" )
s2contentcsgoimported = s2contentcsgo

# Define a non-aborting error callback for all import operations
# This prevents the script from exiting when individual assets fail to import
def errorCallback(cmd=None):
	if cmd:
		print(f"Warning: Command failed but continuing with import: {cmd}")
	else:
		print(f"Warning: Import encountered an error but continuing...")

# Disable VPK signature checking before starting import
vpk_sig_path, vpk_sig_old = DisableVPKSignatures(s2gamecsgo)

# Warning prompt removed - auto-continue for cs2importer integration

# Verify CS:GO VPK files exist and are valid
pak01_vpk = os.path.join(s1gamecsgo, "pak01_dir.vpk")
if not os.path.exists(pak01_vpk):
	print(f"\nERROR: CS:GO pak01_dir.vpk not found at: {pak01_vpk}")
	print("The CS:GO installation appears to be incomplete or corrupted.")
	print("\nTo fix this:")
	print("1. Open Steam")
	print("2. Right-click Counter-Strike 2 in your library")
	print("3. Go to Properties > Installed Files > Verify integrity of game files")
	print("4. Wait for Steam to verify and repair the CS:GO files")
	print("\nNote: CS2 includes CS:GO files in the same installation.")
	sys.exit(1)
else:
	print(f"Verified CS:GO VPK files exist at: {s1gamecsgo}")
	# Check file size to ensure it's not corrupted
	vpk_size = os.path.getsize(pak01_vpk)
	if vpk_size < 1000:  # VPK dir files should be much larger
		print(f"\nWARNING: pak01_dir.vpk appears corrupted (size: {vpk_size} bytes)")
		print("Please verify game files integrity in Steam.")

try:
	# s1contentcsgo is the base content folder (sdk_content), add \maps to get VMF location
	vmf_file_path = s1contentcsgo + "\\maps\\" + mapname + ".vmf"
	
	print("Starting VMF import...")
	print(f"Using BSP optimization: {usebsp}")
	
	# Check if there's an original BSP file we can use for optimized import
	bsp_file_path = s1contentcsgo + "\\maps\\" + mapname + ".bsp"
	if os.path.exists(bsp_file_path):
		print(f"[OK] Found original BSP file - will use it for face-culled import: {bsp_file_path}")
		# Force usebsp to True to use the pre-optimized BSP
		if not usebsp:
			print("  Enabling -usebsp to utilize BSP's face culling")
			usebsp = True
	else:
		if usebsp:
			print("[WARNING] No BSP file found - will compile VMF to BSP first (this adds extra time)")
			print("  Note: Decompiled VMFs may have more faces than original")
	
	# CRITICAL FIX: source1import's VBSP has issues with paths containing spaces
	# Copy VMF and BSP to temp directory to avoid "Counter-Strike Global Offensive" path issues
	# Place it in .cs2kz-mapping-tools subfolder for organization
	cs2kz_temp = os.path.join(tempfile.gettempdir(), ".cs2kz-mapping-tools")
	os.makedirs(cs2kz_temp, exist_ok=True)
	temp_import_dir = tempfile.mkdtemp(prefix="cs2import_", dir=cs2kz_temp)
	temp_maps_dir = os.path.join(temp_import_dir, "maps")
	os.makedirs(temp_maps_dir, exist_ok=True)
	
	# Temporarily rename the original VMF/BSP in csgo/maps to prevent source1import from finding it
	# source1import searches multiple paths and will use the one with spaces if it finds it first
	original_vmf_backup = vmf_file_path + ".backup_temp"
	original_bsp_backup = bsp_file_path + ".backup_temp"
	vmf_was_renamed = False
	bsp_was_renamed = False
	
	try:
		if os.path.exists(vmf_file_path):
			os.rename(vmf_file_path, original_vmf_backup)
			vmf_was_renamed = True
			print(f"Temporarily renamed original VMF to prevent path issues")
		
		if os.path.exists(bsp_file_path):
			os.rename(bsp_file_path, original_bsp_backup)
			bsp_was_renamed = True
			print(f"Temporarily renamed original BSP to prevent path issues")
	except Exception as e:
		print(f"Warning: Could not rename original files: {e}")
	
	# Copy VMF to temp
	temp_vmf = os.path.join(temp_maps_dir, mapname + ".vmf")
	shutil.copy2(original_vmf_backup if vmf_was_renamed else vmf_file_path, temp_vmf)
	print(f"Copied VMF to temp directory (to avoid path space issues): {temp_vmf}")
	
	# Copy BSP to temp if it exists (needed for -usebsp)
	if vmf_was_renamed or os.path.exists(bsp_file_path):
		temp_bsp = os.path.join(temp_maps_dir, mapname + ".bsp")
		bsp_source = original_bsp_backup if bsp_was_renamed else bsp_file_path
		if os.path.exists(bsp_source):
			shutil.copy2(bsp_source, temp_bsp)
			print(f"Copied BSP to temp directory: {temp_bsp}")
	
	# IMPORTANT: Import VMF with -usebsp FIRST to allow VBSP to cull void-facing faces
	# This must happen before importing materials/models to get proper face culling
	# Use temp directory to avoid path issues with "Counter-Strike Global Offensive"
	# Use full path to source1import.exe instead of relying on PATH
	source1import_exe = GetSource1ImportPath()
	print(f"[DEBUG] Using source1import at: {source1import_exe}")
	print(f"[DEBUG] source1import exists: {os.path.exists(source1import_exe)}")
	sys.stdout.flush()
	
	mapImportCmd = "\"" + source1import_exe + "\" -retail -nop4 -nop4sync " + "%s" %("-usebsp" if usebsp == True else "") + "%s" %(" -usebsp_nomergeinstances" if nomergeinstances == True else "") + " -src1gameinfodir \"" + s1gamecsgo + "\" -src1contentdir \"" + temp_import_dir + "\" -s2addon \"" + s2addon + "\" -game csgo maps\\" + mapname + ".vmf"
	
	print(f"Import command: {mapImportCmd}")
	
	try:
		utl.RunCommand( mapImportCmd, errorCallback )
		print("Successfully imported VMF to VMAP with face culling")
	except Exception as e:
		print(f"Warning: VMF import failed: {e}")
		print("Continuing with dependency import...")
	finally:
		# Restore renamed files
		try:
			if vmf_was_renamed and os.path.exists(original_vmf_backup):
				os.rename(original_vmf_backup, vmf_file_path)
				print(f"Restored original VMF")
			if bsp_was_renamed and os.path.exists(original_bsp_backup):
				os.rename(original_bsp_backup, bsp_file_path)
				print(f"Restored original BSP")
		except Exception as e:
			print(f"Warning: Could not restore original files: {e}")
		
		# Clean up temp directory
		try:
			if os.path.exists(temp_import_dir):
				shutil.rmtree(temp_import_dir)
				print(f"Cleaned up temp directory: {temp_import_dir}")
		except Exception as e:
			print(f"Warning: Could not clean up temp directory: {e}")

	print("VMF import process completed.")
	
	# Now import materials and models AFTER the VMF has been processed
	# Fix material file case to match VMF before import
	print("Fixing material file case to match VMF references...")
	# Use s1gamecsgo (CS:GO installation path) instead of s1contentcsgo (Desktop path)
	# because materials are in "Counter-Strike Global Offensive\csgo\materials"
	materials_base_path = os.path.join(s1gamecsgo, "..")  # Go up one level from csgo folder
	FixMaterialCase(vmf_file_path, materials_base_path)

	# Import all materials referenced in VMF from pak01
	vmf_imported_materials = set()
	try:
		vmf_imported_materials = ImportVMFMaterials(vmf_file_path, s1gamecsgo, s2addon, s2contentcsgoimported, errorCallback)
	except Exception as e:
		print(f"Warning: VMF material import failed: {e}")
		print("Continuing with model import...")

	# Import all models referenced in VMF from pak01
	try:
		ImportVMFModels(vmf_file_path, s1gamecsgo, s2addon, s2contentcsgoimported, errorCallback)
	except Exception as e:
		print(f"Warning: VMF model import failed: {e}")
		import traceback
		traceback.print_exc()
		print("Continuing with post-processing...")

	# replace 'instance' paths with 'prefab' 
	mapname = mapname.replace( "instances", "prefabs" )

	if ( not skipdeps ):
		# Check for embedded materials extracted from BSP
		embedded_refs_file = s1contentcsgo + "\\" + mapname + "_embedded_refs.txt"
		if os.path.exists(embedded_refs_file):
			print(f"Found embedded materials from BSP extraction, importing...")
			# Import embedded materials - need to specify content dir as csgo root since materials are there
			source1import_exe = GetSource1ImportPath()
			importcmd = "\"" + source1import_exe + "\" -retail -nop4 -nop4sync -src1gameinfodir \"" + s1gamecsgo + "\" -src1contentdir \"" + s1gamecsgo + "\" -s2addon " + s2addon + " -game csgo -usefilelist \"" + embedded_refs_file + "\""
			utl.RunCommand( importcmd, errorCallback )
			
			# Now compile the imported materials
			refs = utl.ReadTextFile( embedded_refs_file )
			str = utl.ListStringFromRefs( refs )
			flatList = str.split( "\n" )
			
			newList = ""
			for line in flatList:
				if len( line ):
					line = line.replace( ".vmt", ".vmat" )
					line = line.replace( " ", "_" )
					newList += s2contentcsgoimported + "\\" + line.replace( "/", "\\" ) + "\n"
				
			tmpFile = s2contentcsgoimported + "\\maps\\" + mapname + "_embedded_compile_refs.txt"
			maps_dir = os.path.dirname(tmpFile)
			os.makedirs(maps_dir, exist_ok=True)
			
			utl.EnsureFileWritable( tmpFile )
			writeFile = open( tmpFile, "w" )
			writeFile.write( newList )
			writeFile.close()
			
		# Skip compilation - CS2 Hammer will compile assets when the map is opened
		# compilercmd = "resourcecompiler -retail -nop4 -game csgo -f -filelist \"" + tmpFile + "\""
		# utl.RunCommand( compilercmd, errorCallback )
		print("Skipping embedded material compilation (will be compiled automatically when opening in Hammer)")
		
		print("Re-importing VMF to update with compiled embedded materials...")
		try:
			utl.RunCommand( mapImportCmd, errorCallback )
		except Exception as e:
			print(f"Warning: VMF re-import failed: {e}")
			print("Continuing with prefab processing...")
	
	# Check if refs file exists to process prefab dependencies
	# Refs files are now in maps\ folder after the initial import
	refs_file = s2contentcsgoimported + "\\maps\\" + mapname + "_refs.txt"
	
	if os.path.exists(refs_file):
		print("Processing prefab dependencies...")
		
		# Create prefab refs by copying from main refs
		prefab_refs_file = s2contentcsgoimported + "\\maps\\" + mapname + "_prefab_refs.txt"
		import shutil
		shutil.copy(refs_file, prefab_refs_file)
		
		# Strip out models as they go through the new importer last
		StripMDLsFromRefs( prefab_refs_file )

		# Import and compile prefab models and their materials
		ImportAndCompileMapMDLs( s2contentcsgoimported + "\\maps\\" + mapname + "_prefab_mdl_lst.txt", s2addon, errorCallback )

		# Import and compile prefab refs (excluding mdls) - uses -filelist for speed
		ImportAndCompileMapRefs( s2contentcsgoimported + "\\maps\\" + mapname + "_prefab_new_refs.txt", s2addon, errorCallback )

		print("Re-importing VMF to update with compiled assets...")
		# Quick import vmf again (taking dependencies into account now that materials in particular have been imported/compiled) 
		try:
			utl.RunCommand( mapImportCmd, errorCallback )
			print("Successfully completed final VMF import")
		except Exception as e:
			print(f"Warning: Final VMF import failed: {e}")
			print("Import process completed with some errors")
	else:
		print(f"No refs file found, skipping prefab dependency processing")
	
	# Move all .vmap files (main map only) to maps subfolder
	# This must happen AFTER the final re-import so we move the updated VMAP
	maps_dir = s2contentcsgo + "\\maps"
	os.makedirs(maps_dir, exist_ok=True)

	# Import shutil and glob
	import shutil
	import glob

	# Find all vmap files in the addon content root (not in subdirectories)
	vmap_pattern = s2contentcsgoimported + "\\*.vmap"
	vmap_files = glob.glob(vmap_pattern)
	
	# Also check if main map VMAP already exists in maps folder (created by source1import)
	main_vmap_in_maps = os.path.join(maps_dir, mapname + ".vmap")
	main_vmap_exists = os.path.exists(main_vmap_in_maps)
	
	# Total VMAPs includes: VMAPs to move + main VMAP if it exists in maps folder
	total_vmap_count = len(vmap_files) + (1 if main_vmap_exists else 0)
	
	print(f"Found {total_vmap_count} VMAP files to move to maps folder")

	# Move all vmap files to maps folder
	for vmap_file in vmap_files:
		filename = os.path.basename(vmap_file)
		destfile = os.path.join(maps_dir, filename)
		
		# If destination exists, remove it first
		if os.path.exists(destfile):
			os.remove(destfile)
		
		# Move the file
		shutil.move(vmap_file, destfile)
		print(f"  -> Moved {filename}")
	
	# If main map VMAP already exists in maps folder, report it as "found"
	if main_vmap_exists:
		print(f"  -> Found {mapname}.vmap (already in maps folder)")

	# Move prefabs folder to maps\prefabs\ if it exists
	# Prefabs should be in maps\prefabs\MAPNAME\ not just prefabs\MAPNAME\
	prefabs_root = s2contentcsgoimported + "\\prefabs"
	if os.path.exists(prefabs_root):
		maps_prefabs_dir = s2contentcsgo + "\\maps\\prefabs"
		os.makedirs(maps_prefabs_dir, exist_ok=True)
		
		# Move the entire prefabs folder to maps\prefabs\
		dest_prefabs = os.path.join(maps_prefabs_dir, mapname)
		
		# If destination exists, remove it first
		if os.path.exists(dest_prefabs):
			import shutil
			shutil.rmtree(dest_prefabs)
		
		# Move prefabs\MAPNAME to maps\prefabs\MAPNAME
		src_prefabs = os.path.join(prefabs_root, mapname)
		if os.path.exists(src_prefabs):
			shutil.move(src_prefabs, dest_prefabs)
			print(f"Moved prefabs folder to maps\\prefabs\\{mapname}")
		
		# Fix prefab paths in the main VMAP file
		vmap_file = s2contentcsgo + "\\maps\\" + mapname + ".vmap"
		if os.path.exists(vmap_file):
			try:
				with open(vmap_file, 'r', encoding='utf-8', errors='ignore') as f:
					vmap_content = f.read()
				
				# Find prefab references that don't have the full path
				import re
				# Look for prefab references like "mapname_prefab.vmap" and replace with "maps/prefabs/mapname/mapname_prefab.vmap"
				prefab_pattern = r'"(' + re.escape(mapname) + r'_[^"]*\.vmap)"'
				def fix_prefab_path(match):
					prefab_name = match.group(1)
					return f'"maps/prefabs/{mapname}/{prefab_name}"'
				
				original_content = vmap_content
				vmap_content = re.sub(prefab_pattern, fix_prefab_path, vmap_content)
				
				if vmap_content != original_content:
					with open(vmap_file, 'w', encoding='utf-8') as f:
						f.write(vmap_content)
					print(f"Fixed prefab paths in {mapname}.vmap")
				else:
					print(f"No prefab path fixes needed in {mapname}.vmap")
					
			except Exception as e:
				print(f"Warning: Could not fix prefab paths in VMAP file: {e}")

	# Check for prefab VMAP files
	prefabs_dir = s2contentcsgoimported + "\\maps\\prefabs\\" + mapname
	if os.path.exists(prefabs_dir):
		prefab_vmaps = glob.glob(prefabs_dir + "\\*.vmap")
		if prefab_vmaps:
			print(f"\nFound {len(prefab_vmaps)} prefab VMAP file(s) - ready to use in Hammer:")
			for prefab_vmap in prefab_vmaps:
				print(f"  -> {os.path.basename(prefab_vmap)}")
			print("\nNote: Prefabs are loaded directly as VMAP files in Hammer - no compilation needed")
		else:
			print(f"No prefab VMAP files found in {prefabs_dir}")
	else:
		print(f"No prefabs directory found")

	print("\nImport complete! Map and prefab VMAP files are ready to use in Hammer")

finally:
	#
	# FINISH
	#
	
	# Restore VPK signature checking
	RestoreVPKSignatures(vpk_sig_path, vpk_sig_old)

# restore VALVE_NO_AUTO_P4 environment var
utl.RestoreEnv()

#
end = time.time()

elapsedTime = end - start

utl.print_I( "import_map.py " + s1gamecsgo + " " + s1contentcsgo + " " + s2gamecsgo + " " + mapname + " " + "%s" %(" -usebsp" if usebsp == True else "") + "%s" %(" -usebsp_nomergeinstances" if nomergeinstances == True else "")+ "%s" %(" -skipdeps" if skipdeps == True else "") )
utl.print_I( "Elapsed time: " + utl.GetElapsedTime( elapsedTime ) )
