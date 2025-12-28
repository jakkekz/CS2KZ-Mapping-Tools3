"""
VSND Decompiler using ValveResourceFormat .NET library
Downloads and caches DLLs in temp directory
Uses .NET Core runtime (like Hammer5Tools)
"""

import os
import sys
import tempfile
import urllib.request
from pathlib import Path



# DLL download URLs (from Hammer5Tools)
DLL_URLS = {
    'ValveResourceFormat.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/ValveResourceFormat.dll',
    'ValvePak.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/ValvePak.dll',
    'ValveKeyValue.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/ValveKeyValue.dll',
    'ZstdSharp.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/ZstdSharp.dll',
    'System.IO.Hashing.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/System.IO.Hashing.dll',
    'K4os.Compression.LZ4.dll': 'https://github.com/dertwist/Hammer5Tools/raw/main/src/external/K4os.Compression.LZ4.dll',
}

class VSNDDecompiler:
    def __init__(self):
        self.dll_dir = Path(tempfile.gettempdir()) / '.CS2KZ-mapping-tools' / 'dlls'
        self.initialized = False
        self.Resource = None
        self.FileExtract = None
        self.Package = None
        
    def ensure_dlls(self):
        """Download DLLs if they don't exist"""
        os.makedirs(self.dll_dir, exist_ok=True)
        
        for dll_name, url in DLL_URLS.items():
            dll_path = self.dll_dir / dll_name
            if not dll_path.exists():
                print(f"Downloading {dll_name}...")
                try:
                    urllib.request.urlretrieve(url, str(dll_path))
                    print(f"✓ Downloaded {dll_name}")
                except Exception as e:
                    print(f"✗ Failed to download {dll_name}: {e}")
                    return False
        return True
    
    def initialize(self):
        """Initialize .NET Core runtime and load assemblies (Hammer5Tools method)"""
        if self.initialized:
            return True
            
        if not self.ensure_dlls():
            return False
        
        try:
            # Initialize pythonnet with .NET Core (KEY: this is what Hammer5Tools does!)
            from pythonnet import load
            load("coreclr")
            
            import clr
            import System
            from System.IO import MemoryStream
            
            # Add DLL directory to PATH for assembly resolution
            dll_dir_str = str(self.dll_dir)
            os.environ["PATH"] = dll_dir_str + os.pathsep + os.environ.get("PATH", "")
            
            # Load dependencies first (order matters!)
            clr.AddReference(str(self.dll_dir / "K4os.Compression.LZ4.dll"))
            clr.AddReference(str(self.dll_dir / "System.IO.Hashing.dll"))
            clr.AddReference(str(self.dll_dir / "ValveKeyValue.dll"))
            clr.AddReference(str(self.dll_dir / "ZstdSharp.dll"))
            clr.AddReference(str(self.dll_dir / "ValvePak.dll"))
            
            # Load main VRF assembly
            clr.AddReference(str(self.dll_dir / "ValveResourceFormat.dll"))
            
            # Get required types
            from System.Reflection import Assembly
            vrf_assembly = Assembly.LoadFrom(str(self.dll_dir / "ValveResourceFormat.dll"))
            valvepak_assembly = Assembly.LoadFrom(str(self.dll_dir / "ValvePak.dll"))
            
            # Find types
            self.Resource = vrf_assembly.GetType("ValveResourceFormat.Resource")
            self.FileExtract = vrf_assembly.GetType("ValveResourceFormat.IO.FileExtract")
            
            # Try both possible Package type names
            self.Package = valvepak_assembly.GetType("SteamDatabase.ValvePak.Package")
            if not self.Package:
                self.Package = valvepak_assembly.GetType("ValvePak.Package")
            
            if not self.Resource or not self.FileExtract or not self.Package:
                print("✗ Could not find required .NET types")
                return False
            
            self.initialized = True
            print("✓ VSND decompiler initialized with .NET Core")
            return True
            
        except Exception as e:
            error_str = str(e)
            
            # Check for common .NET Runtime missing errors
            if "MemoryMarshal" in error_str or "TypeLoadException" in error_str or "Could not load type" in error_str:
                print("✗ .NET 8 Runtime is required for internal CS2 sound decompilation")
                print("  Download: https://dotnet.microsoft.com/download/dotnet/8.0/runtime")
                print("  Install: .NET Desktop Runtime 8.0 (x64)")
                print("  Note: Custom sound files work without .NET Runtime")
            else:
                print(f"✗ Failed to initialize .NET: {e}")
                
            import traceback
            traceback.print_exc()
            return False
    
    def decompile_vsnd(self, vpk_path, internal_sound_path, output_path):
        """
        Decompile .vsnd_c file from VPK to .wav or .mp3 (Hammer5Tools method)
        
        Args:
            vpk_path: Path to pak01_dir.vpk
            internal_sound_path: Path inside VPK (e.g., 'sounds/items/healthshot_thud_01.vsnd_c')
            output_path: Where to save the decompiled audio
            
        Returns:
            Path to output file or None if failed
        """
        if not self.initialized and not self.initialize():
            return None
        
        try:
            import System
            from System.IO import MemoryStream
            from System import Array, Byte
            from System.Reflection import BindingFlags
            
            # Open VPK and extract file
            package = System.Activator.CreateInstance(self.Package)
            try:
                package.Read(vpk_path)
                
                # Normalize path - VPK uses forward slashes
                normalized_path = internal_sound_path.replace("\\", "/")
                file_entry = package.FindEntry(normalized_path)
                
                if not file_entry:
                    print(f"✗ File not found in VPK: {normalized_path}")
                    print(f"  Tried path: {normalized_path}")
                    return None
                
                # Find ReadEntry method
                read_method = None
                methods = self.Package.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                for method in methods:
                    if method.Name == "ReadEntry":
                        params = method.GetParameters()
                        if len(params) >= 2:
                            read_method = method
                            break
                
                if not read_method:
                    print("✗ Could not find ReadEntry method")
                    return None
                
                # Invoke ReadEntry to get file data
                params = read_method.GetParameters()
                args = System.Array.CreateInstance(System.Object, len(params))
                args[0] = file_entry
                args[1] = System.Array.CreateInstance(Byte, 0)
                if len(params) > 2:
                    args[2] = True  # validateCrc
                
                read_method.Invoke(package, args)
                data = args[1]  # out parameter contains the data
                
                # Convert to Python bytes if needed
                if not isinstance(data, bytes):
                    data = bytes([data[i] for i in range(data.Length)])
                
                # Create resource and load data
                resource = System.Activator.CreateInstance(self.Resource)
                memory_stream = MemoryStream(data)
                
                try:
                    resource.Read(memory_stream)
                    
                    # Find Extract method (static method on FileExtract)
                    extract_method = None
                    methods = self.FileExtract.GetMethods(BindingFlags.Public | BindingFlags.Static)
                    for method in methods:
                        if method.Name == "Extract":
                            extract_method = method
                            break
                    
                    if not extract_method:
                        print("✗ Could not find FileExtract.Extract method")
                        return None
                    
                    # Invoke Extract (static method)
                    extract_params = extract_method.GetParameters()
                    extract_args = System.Array.CreateInstance(System.Object, len(extract_params))
                    extract_args[0] = resource
                    for i in range(1, len(extract_params)):
                        extract_args[i] = None
                    
                    content_file = extract_method.Invoke(None, extract_args)
                    
                    if content_file and hasattr(content_file, 'Data') and content_file.Data:
                        # Determine output format
                        ext = 'wav'
                        if hasattr(content_file, 'FileName') and content_file.FileName:
                            file_ext = os.path.splitext(str(content_file.FileName))[1][1:]
                            if file_ext:
                                ext = file_ext
                        elif hasattr(content_file, 'Type') and str(content_file.Type).lower() == 'mp3':
                            ext = 'mp3'
                        
                        # Save file
                        output_file = output_path.replace('.wav', f'.{ext}').replace('.mp3', f'.{ext}')
                        os.makedirs(os.path.dirname(output_file), exist_ok=True)
                        
                        out_bytes = bytes([content_file.Data[i] for i in range(content_file.Data.Length)])
                        with open(output_file, 'wb') as f:
                            f.write(out_bytes)
                        
                        print(f"✓ Decompiled {internal_sound_path} to {output_file} ({len(out_bytes)} bytes)")
                        return output_file
                    else:
                        print("✗ Failed to extract content from .vsnd_c file")
                        return None
                
                finally:
                    memory_stream.Dispose()
                    if hasattr(resource, 'Dispose'):
                        resource.Dispose()
            
            finally:
                if hasattr(package, 'Dispose'):
                    package.Dispose()
            
            return None
            
        except Exception as e:
            print(f"✗ Error decompiling vsnd: {e}")
            import traceback
            traceback.print_exc()
            return None
