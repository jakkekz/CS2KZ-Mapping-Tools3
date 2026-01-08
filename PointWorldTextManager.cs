using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using Microsoft.Win32;

namespace CS2KZMappingTools
{
    public class PointWorldTextManager
    {
        private readonly string charsFolder;
        private readonly Dictionary<string, Bitmap> characterImages;
        
        public event Action<string>? LogMessage;
        public event Action<string>? LogEvent;

        public PointWorldTextManager(string? customCharsFolder = null)
        {
            if (customCharsFolder != null)
            {
                charsFolder = customCharsFolder;
            }
            else
            {
                // Use the chars folder in the project root (4 levels up from bin directory)
                var exeDir = AppDomain.CurrentDomain.BaseDirectory;
                var projectRoot = Path.GetFullPath(Path.Combine(exeDir, "..", "..", "..", ".."));
                charsFolder = Path.Combine(projectRoot, "chars");
                Log($"Using chars folder path: {charsFolder}");
            }
            
            characterImages = new Dictionary<string, Bitmap>();
            Log($"PointWorldTextManager initialized. Chars folder path: {charsFolder}");
            LoadCharacterImages();
        }

        private void Log(string message)
        {
            LogMessage?.Invoke(message);
            LogEvent?.Invoke(message);
        }

        private string? FindCs2Path()
        {
            try
            {
                // Get Steam path from registry
                using var key = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam");
                if (key?.GetValue("SteamPath") is string steamPath)
                {
                    // Try both casings for libraryfolders.vdf
                    var libraryFoldersPath = Path.Combine(steamPath, "steamapps", "libraryfolders.vdf");
                    if (!File.Exists(libraryFoldersPath))
                    {
                        libraryFoldersPath = Path.Combine(steamPath, "SteamApps", "libraryfolders.vdf");
                    }
                    
                    var cs2Path = FindCs2LibraryPath(libraryFoldersPath);

                    if (!string.IsNullOrEmpty(cs2Path))
                    {
                        // Try both casings for appmanifest
                        var appManifestPath = Path.Combine(cs2Path, "steamapps", "appmanifest_730.acf");
                        if (!File.Exists(appManifestPath))
                        {
                            appManifestPath = Path.Combine(cs2Path, "SteamApps", "appmanifest_730.acf");
                        }
                        
                        if (File.Exists(appManifestPath))
                        {
                            // Parse the VDF file to get install directory
                            var installDir = ParseAppManifest(appManifestPath);
                            if (!string.IsNullOrEmpty(installDir))
                            {
                                // Try both casings for common folder
                                cs2Path = Path.Combine(cs2Path, "steamapps", "common", installDir);
                                if (!Directory.Exists(cs2Path))
                                {
                                    var steamAppsPath = cs2Path.Replace("steamapps", "SteamApps");
                                    if (Directory.Exists(steamAppsPath))
                                    {
                                        cs2Path = steamAppsPath;
                                    }
                                }
                                Log($"Found CS2 at: {cs2Path}");
                                return cs2Path;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Error finding CS2 path: {ex.Message}");
            }

            Log("Could not find CS2 installation automatically");
            return null;
        }

        private string? FindCs2LibraryPath(string libraryFoldersPath)
        {
            if (!File.Exists(libraryFoldersPath))
            {
                return null;
            }

            try
            {
                // Check default Steam location first
                var steamPath = Path.GetDirectoryName(Path.GetDirectoryName(libraryFoldersPath));
                if (!string.IsNullOrEmpty(steamPath))
                {
                    var defaultManifest = Path.Combine(steamPath, "steamapps", "appmanifest_730.acf");
                    if (!File.Exists(defaultManifest))
                    {
                        defaultManifest = Path.Combine(steamPath, "SteamApps", "appmanifest_730.acf");
                    }
                    if (File.Exists(defaultManifest))
                    {
                        return steamPath;
                    }
                }
                
                // Check all library folders
                var content = File.ReadAllText(libraryFoldersPath);
                var lines = content.Split('\n');
                
                foreach (var line in lines)
                {
                    var trimmed = line.Trim();
                    if (trimmed.Contains("\"path\""))
                    {
                        var match = Regex.Match(trimmed, "\"path\"\\s+\"([^\"]+)\"");
                        if (match.Success)
                        {
                            var libraryPath = match.Groups[1].Value.Replace("\\\\", "\\");
                            
                            // Check if this library has CS2
                            var manifestPath = Path.Combine(libraryPath, "steamapps", "appmanifest_730.acf");
                            if (!File.Exists(manifestPath))
                            {
                                manifestPath = Path.Combine(libraryPath, "SteamApps", "appmanifest_730.acf");
                            }
                            
                            if (File.Exists(manifestPath))
                            {
                                return libraryPath;
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Error parsing library folders: {ex.Message}");
            }

            return null;
        }

        private string? ParseAppManifest(string appManifestPath)
        {
            try
            {
                var content = File.ReadAllText(appManifestPath);
                var match = Regex.Match(content, "\"installdir\"\\s+\"([^\"]+)\"");
                return match.Success ? match.Groups[1].Value : null;
            }
            catch (Exception ex)
            {
                Log($"Error parsing app manifest: {ex.Message}");
            }
            return null;
        }

        private void LoadCharacterImages()
        {
            try
            {
                Log($"Loading character images from: {charsFolder}");
                Log($"Directory exists: {Directory.Exists(charsFolder)}");
                Log($"AppDomain.CurrentDomain.BaseDirectory: {AppDomain.CurrentDomain.BaseDirectory}");
                
                if (!Directory.Exists(charsFolder))
                {
                    Log($"Characters folder not found: {charsFolder}");
                    return;
                }

                var pngFiles = Directory.GetFiles(charsFolder, "*.png");
                Log($"Found {pngFiles.Length} PNG files in characters folder");

                foreach (var file in pngFiles)
                {
                    try
                    {
                        var filename = Path.GetFileNameWithoutExtension(file);
                        string? charKey = GetCharacterKey(filename);
                        
                        Log($"Processing file: {filename}.png -> key: {charKey ?? "null"}");
                        
                        if (charKey != null)
                        {
                            var bitmap = new Bitmap(file);
                            characterImages[charKey] = bitmap;
                            Log($"✓ Loaded character '{charKey}' from {filename}.png");
                        }
                        else
                        {
                            Log($"✗ Skipped {filename}.png (no valid key mapping)");
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"Failed to load character image {file}: {ex.Message}");
                    }
                }

                Log($"Successfully loaded {characterImages.Count} character images");
                Log($"Available character keys: {string.Join(", ", characterImages.Keys)}");
            }
            catch (Exception ex)
            {
                Log($"Error loading character images: {ex.Message}");
            }
        }

        private string? GetCharacterKey(string filename)
        {
            // 1. Check for prefixed digits (e.g., '_1.png' -> key '_1')
            if (filename.StartsWith("_") && filename.Length == 2 && char.IsDigit(filename[1]))
            {
                return filename; // Return '_1' not '1'
            }

            // 2. Check for symbols (e.g., '33.png' -> key '!')
            if (int.TryParse(filename, out int ascii) && ascii >= 32 && ascii <= 126)
            {
                return ((char)ascii).ToString();
            }

            // 3. Check for lowercase letters (e.g., 'a.png' -> key 'a')
            if (filename.Length == 1 && char.IsLower(filename[0]))
            {
                return filename;
            }

            // 4. Check for uppercase/double letters (e.g., 'aa.png' -> key 'aa' for 'A')
            if (filename.Length == 2 && filename[0] == filename[1] && char.IsLower(filename[0]))
            {
                return filename;
            }

            // 5. Check for space character (e.g., '_.png' -> key '_')
            if (filename == "_")
            {
                return "_";
            }

            return null;
        }

        public async Task<string?> GenerateTextWithOptionsAsync(string text, string outputPath, 
            int canvasWidth, int canvasHeight, bool generateVmat, string? addonName, string? customFilename = null, float scaleFactor = 1.0f)
        {
            return await Task.Run(() => GenerateTextWithOptions(text, outputPath, canvasWidth, canvasHeight, generateVmat, addonName, customFilename, scaleFactor));
        }

        public string? GenerateTextWithOptions(string text, string outputPath, 
            int canvasWidth, int canvasHeight, bool generateVmat, string? addonName, string? customFilename = null, float scaleFactor = 1.0f)
        {
            try
            {
                // Determine the actual output directory and filename
                string actualOutputPath;
                string fileNameWithoutExtension;

                if (!string.IsNullOrEmpty(addonName))
                {
                    // Find CS2 path dynamically
                    var cs2Path = FindCs2Path();
                    if (string.IsNullOrEmpty(cs2Path))
                    {
                        Log("Could not find CS2 installation path");
                        return null;
                    }

                    // Use addon directory
                    var addonPath = Path.Combine(cs2Path, "content", "csgo_addons", addonName, "materials", "point_worldtext");
                    
                    // Create directory if it doesn't exist
                    Directory.CreateDirectory(addonPath);
                    
                    // Generate filename from text (sanitize for filesystem)
                    var sanitizedText = SanitizeFileName(text);
                    fileNameWithoutExtension = !string.IsNullOrEmpty(customFilename) ? SanitizeFileName(customFilename) : SanitizeFileName(text);
                    actualOutputPath = Path.Combine(addonPath, $"{fileNameWithoutExtension}.png");
                    
                    Log($"Using addon path: {actualOutputPath}");
                }
                else
                {
                    // Use custom path
                    actualOutputPath = outputPath;
                    fileNameWithoutExtension = Path.GetFileNameWithoutExtension(actualOutputPath);
                    Log($"Using custom path: {actualOutputPath}");
                }

                // Generate the main PNG image
                var result = StitchText(text, actualOutputPath, 0.5, scaleFactor, canvasWidth, canvasHeight);
                if (result == null)
                {
                    return null;
                }

                if (generateVmat)
                {
                    Log("Generating .vmat file and alpha mask...");
                    
                    // Generate alpha mask
                    var alphaPath = Path.Combine(Path.GetDirectoryName(actualOutputPath)!, 
                        $"{fileNameWithoutExtension}_alpha.png");
                    GenerateAlphaMask(actualOutputPath, alphaPath);
                    
                    // Generate .vmat file
                    var vmatPath = Path.Combine(Path.GetDirectoryName(actualOutputPath)!, 
                        $"{fileNameWithoutExtension}.vmat");
                    GenerateVmatFile(fileNameWithoutExtension, vmatPath);
                    
                    Log($"✓ Generated .vmat file: {vmatPath}");
                    Log($"✓ Generated alpha mask: {alphaPath}");
                }

                return result;
            }
            catch (Exception ex)
            {
                Log($"Error in GenerateTextWithOptions: {ex.Message}");
                return null;
            }
        }

        private string SanitizeFileName(string text)
        {
            // Remove or replace invalid filename characters
            var invalid = Path.GetInvalidFileNameChars();
            var sanitized = string.Join("_", text.Split(invalid, StringSplitOptions.RemoveEmptyEntries));
            
            // Limit length and make lowercase
            if (sanitized.Length > 50)
            {
                sanitized = sanitized.Substring(0, 50);
            }
            
            return sanitized.ToLower().Trim('_');
        }

        private void GenerateAlphaMask(string originalImagePath, string alphaMaskPath)
        {
            using var originalImage = new Bitmap(originalImagePath);
            using var alphaMask = new Bitmap(originalImage.Width, originalImage.Height, PixelFormat.Format24bppRgb);
            using var graphics = Graphics.FromImage(alphaMask);
            
            // Fill entire background with black first
            graphics.Clear(Color.Black);
            
            // Go through each pixel and make non-transparent areas white
            for (int x = 0; x < originalImage.Width; x++)
            {
                for (int y = 0; y < originalImage.Height; y++)
                {
                    var pixel = originalImage.GetPixel(x, y);
                    
                    // If pixel has significant opacity (not transparent background), make it white
                    // Use threshold to handle anti-aliasing better
                    if (pixel.A > 128) // More than 50% opaque
                    {
                        alphaMask.SetPixel(x, y, Color.White);
                    }
                    // Pixels with alpha <= 128 stay black (background)
                }
            }
            
            alphaMask.Save(alphaMaskPath, ImageFormat.Png);
        }

        private void GenerateVmatFile(string fileNameBase, string vmatPath)
        {
            var vmatContent = $@"// THIS FILE IS AUTO-GENERATED

Layer0
{{
	shader ""csgo_static_overlay.vfx""

	//---- Blend Mode ----
	F_BLEND_MODE 1 // Translucent

	//---- Color ----
	g_flModelTintAmount ""1.000""
	g_flTexCoordRotation ""0.000""
	g_fTextureColorBrightness ""1.000""
	g_fTextureColorContrast ""1.000""
	g_fTextureColorSaturation ""1.000""
	g_nScaleTexCoordUByModelScaleAxis ""0"" // None
	g_nScaleTexCoordVByModelScaleAxis ""0"" // None
	g_vColorTint ""[1.000000 1.000000 1.000000 0.000000]""
	g_vTexCoordCenter ""[0.500 0.500]""
	g_vTexCoordOffset ""[0.000 0.000]""
	g_vTexCoordScale ""[1.000 1.000]""
	g_vTexCoordScrollSpeed ""[0.000 0.000]""
	g_vTextureColorCorrectionTint ""[1.000000 1.000000 1.000000 0.000000]""
	TextureColor ""materials/point_worldtext/{fileNameBase}.png""

	//---- Fog ----
	g_bFogEnabled ""1""

	//---- Texture Address Mode ----
	g_nTextureAddressModeU ""0"" // Wrap
	g_nTextureAddressModeV ""0"" // Wrap

	//---- Translucent ----
	g_flOpacityScale ""1.000""
	TextureTranslucency ""materials/point_worldtext/{fileNameBase}_alpha.png""


	VariableState
	{{
		""Color""
		{{
			""Color Correction"" 0
		}}
		""Fog""
		{{
		}}
		""Texture Address Mode""
		{{
		}}
		""Translucent""
		{{
		}}
	}}
}}";
            
            File.WriteAllText(vmatPath, vmatContent);
        }

        public async Task<string?> StitchTextAsync(string text, string outputPath, 
            double spaceWidthRatio = 0.5, double scaleFactor = 1.0, 
            int canvasWidth = 512, int canvasHeight = 512)
        {
            return await Task.Run(() => StitchText(text, outputPath, spaceWidthRatio, scaleFactor, canvasWidth, canvasHeight));
        }

        public string? StitchText(string text, string outputPath, 
            double spaceWidthRatio = 0.5, double scaleFactor = 1.0, 
            int canvasWidth = 512, int canvasHeight = 512)
        {
            try
            {
                Log($"*** StitchText called - characterImages.Count = {characterImages.Count} ***");
                
                // If no images loaded, try loading them again
                if (characterImages.Count == 0)
                {
                    Log("No character images loaded, attempting to reload...");
                    LoadCharacterImages();
                }
                
                Log($"Stitching text: '{text}'");
                Log($"Output: {outputPath}, Canvas: {canvasWidth}x{canvasHeight}");

                if (string.IsNullOrWhiteSpace(text))
                {
                    Log("No text provided for stitching");
                    return null;
                }

                var lines = text.Split('\n');
                const int spacing = 5; // Fixed spacing between characters
                const int lineSpacing = 10; // Spacing between lines

                // Calculate dimensions for each line
                var lineData = new List<LineInfo>();
                int maxLineWidth = 0;
                int totalHeight = 0;

                foreach (var line in lines)
                {
                    var lineInfo = CalculateLineDimensions(line, spacing, spaceWidthRatio);
                    lineData.Add(lineInfo);
                    maxLineWidth = Math.Max(maxLineWidth, lineInfo.Width);
                    totalHeight += lineInfo.Height;
                }

                // Add spacing between lines
                if (lines.Length > 1)
                {
                    totalHeight += lineSpacing * (lines.Length - 1);
                }

                if (maxLineWidth == 0 || totalHeight == 0)
                {
                    Log("No renderable content found");
                    return null;
                }

                Log($"Text dimensions: {maxLineWidth}x{totalHeight}");

                // Create the stitched image at native size
                using var stitchedImg = new Bitmap(maxLineWidth, totalHeight, PixelFormat.Format32bppArgb);
                using var g = Graphics.FromImage(stitchedImg);
                
                g.Clear(Color.Transparent);
                g.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceOver;

                // Render each line
                int yOffset = 0;
                foreach (var lineInfo in lineData)
                {
                    RenderLine(g, lineInfo, yOffset, spacing);
                    yOffset += lineInfo.Height + lineSpacing;
                }

                // Auto-calculate scale factor to fill canvas
                double scaleW = (double)canvasWidth / stitchedImg.Width;
                double scaleH = (double)canvasHeight / stitchedImg.Height;
                double autoScale = Math.Min(scaleW, scaleH);
                double finalScale = scaleFactor * autoScale;

                int scaledW = (int)(stitchedImg.Width * finalScale);
                int scaledH = (int)(stitchedImg.Height * finalScale);

                Log($"Scaling: {finalScale:F2} ({stitchedImg.Width}x{stitchedImg.Height} -> {scaledW}x{scaledH})");

                // Create final canvas
                using var finalCanvas = new Bitmap(canvasWidth, canvasHeight, PixelFormat.Format32bppArgb);
                using var finalG = Graphics.FromImage(finalCanvas);
                
                finalG.Clear(Color.Transparent);
                finalG.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                finalG.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceOver;

                // Calculate position to center the scaled text on the canvas
                int pasteX = Math.Max(0, (canvasWidth - scaledW) / 2);
                int pasteY = Math.Max(0, (canvasHeight - scaledH) / 2);

                // Draw the scaled text onto the center of the fixed-size canvas
                finalG.DrawImage(stitchedImg, new Rectangle(pasteX, pasteY, scaledW, scaledH));

                // Save the final canvas
                Directory.CreateDirectory(Path.GetDirectoryName(outputPath) ?? "");
                finalCanvas.Save(outputPath, ImageFormat.Png);

                Log($"✓ Text image saved to: {outputPath}");
                return outputPath;
            }
            catch (Exception ex)
            {
                Log($"Error stitching text: {ex.Message}");
                return null;
            }
        }

        private LineInfo CalculateLineDimensions(string line, int spacing, double spaceWidthRatio)
        {
            int lineWidth = 0;
            int lineHeight = 0;
            var characters = new List<CharacterInfo>();

            foreach (char c in line)
            {
                var charKey = GetCharacterLookupKey(c);
                
                if (c == ' ')
                {
                    // Handle actual space - use calculated space width
                    characters.Add(new CharacterInfo { 
                        Character = c, 
                        Key = null, 
                        Image = null,
                        IsSpace = true
                    });
                    // Space width will be calculated after we know line height
                }
                else if (charKey != null && characterImages.ContainsKey(charKey))
                {
                    var img = characterImages[charKey];
                    characters.Add(new CharacterInfo { 
                        Character = c, 
                        Key = charKey, 
                        Image = img, 
                        IsSpace = false
                    });
                    lineWidth += img.Width + spacing;
                    lineHeight = Math.Max(lineHeight, img.Height);
                }
                else
                {
                    Log($"Warning: No image found for character '{c}' (key: {charKey ?? "null"})");
                }
            }

            // Calculate effective space width and final line width
            int effectiveSpaceWidth = lineHeight > 0 ? (int)(lineHeight * spaceWidthRatio) : 25;
            
            int finalLineWidth = 0;
            foreach (var charInfo in characters)
            {
                if (charInfo.IsSpace)
                {
                    charInfo.SpaceWidth = effectiveSpaceWidth;
                    finalLineWidth += effectiveSpaceWidth;
                }
                else if (charInfo.Image != null)
                {
                    finalLineWidth += charInfo.Image.Width + spacing;
                }
            }

            return new LineInfo
            {
                Text = line,
                Width = finalLineWidth,
                Height = lineHeight,
                Characters = characters
            };
        }

        private void RenderLine(Graphics g, LineInfo lineInfo, int yOffset, int spacing)
        {
            int xOffset = 0;
            
            foreach (var charInfo in lineInfo.Characters)
            {
                if (charInfo.IsSpace)
                {
                    // Add space width but don't draw anything
                    xOffset += charInfo.SpaceWidth;
                }
                else if (charInfo.Image != null)
                {
                    g.DrawImage(charInfo.Image, xOffset, yOffset);
                    xOffset += charInfo.Image.Width + spacing;
                }
            }
        }

        private string? GetCharacterLookupKey(char c)
        {
            if (c == ' ')
            {
                // Space character should create actual spacing, not use an image
                return null; // This will be handled as actual space
            }
            else if (c == '_')
            {
                // Underscore character maps to underscore image
                return "_"; // Use the _.png file for underscore symbol
            }
            else if (char.IsUpper(c))
            {
                // Map uppercase letters to their lookup key (e.g., 'A' -> 'aa')
                var lower = char.ToLower(c);
                return $"{lower}{lower}";
            }
            else if (char.IsDigit(c))
            {
                // Map digits to their lookup key (e.g., '0' -> '_0')
                return $"_{c}";
            }
            else
            {
                return c.ToString();
            }
        }

        public void Dispose()
        {
            foreach (var bitmap in characterImages.Values)
            {
                bitmap?.Dispose();
            }
            characterImages.Clear();
        }

        private class LineInfo
        {
            public string Text { get; set; } = "";
            public int Width { get; set; }
            public int Height { get; set; }
            public List<CharacterInfo> Characters { get; set; } = new List<CharacterInfo>();
        }

        private class CharacterInfo
        {
            public char Character { get; set; }
            public string? Key { get; set; }
            public Bitmap? Image { get; set; }
            public bool IsSpace { get; set; }
            public int SpaceWidth { get; set; }
        }
    }
}