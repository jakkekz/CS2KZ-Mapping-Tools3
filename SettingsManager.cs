using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using Newtonsoft.Json;

namespace CS2KZMappingTools
{
    public class SettingsManager
    {
        private static SettingsManager? _instance;
        public static SettingsManager Instance => _instance ??= new SettingsManager();

        private readonly string _settingsPath;
        private Settings _settings;

        private SettingsManager()
        {
            string appDataPath = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
            Directory.CreateDirectory(appDataPath);
            _settingsPath = Path.Combine(appDataPath, "settings.json");
            _settings = LoadSettings();
        }

        private Settings LoadSettings()
        {
            try
            {
                if (File.Exists(_settingsPath))
                {
                    string json = File.ReadAllText(_settingsPath);
                    return JsonConvert.DeserializeObject<Settings>(json) ?? new Settings();
                }
            }
            catch { }
            
            return new Settings();
        }

        public void SaveSettings()
        {
            try
            {
                string json = JsonConvert.SerializeObject(_settings, Formatting.Indented);
                File.WriteAllText(_settingsPath, json);
            }
            catch { }
        }

        public string Theme
        {
            get => _settings.Theme;
            set { _settings.Theme = value; SaveSettings(); }
        }

        public Point WindowPosition
        {
            get => _settings.WindowPosition;
            set { _settings.WindowPosition = value; SaveSettings(); }
        }

        public bool CompactMode
        {
            get => _settings.CompactMode;
            set { _settings.CompactMode = value; SaveSettings(); }
        }

        public int GridColumns
        {
            get => _settings.GridColumns;
            set { _settings.GridColumns = value; SaveSettings(); }
        }

        public float WindowOpacity
        {
            get => _settings.WindowOpacity;
            set { _settings.WindowOpacity = value; SaveSettings(); }
        }

        public bool AlwaysOnTop
        {
            get => _settings.AlwaysOnTop;
            set { _settings.AlwaysOnTop = value; SaveSettings(); }
        }

        public Dictionary<string, bool> ButtonVisibility
        {
            get => _settings.ButtonVisibility;
            set { _settings.ButtonVisibility = value; SaveSettings(); }
        }

        public List<string> ButtonOrder
        {
            get => _settings.ButtonOrder;
            set { _settings.ButtonOrder = value; SaveSettings(); }
        }

        public bool AutoUpdateSource2Viewer
        {
            get => _settings.AutoUpdateSource2Viewer;
            set { _settings.AutoUpdateSource2Viewer = value; SaveSettings(); }
        }

        public bool AutoUpdateMetamod
        {
            get => _settings.AutoUpdateMetamod;
            set { _settings.AutoUpdateMetamod = value; SaveSettings(); }
        }

        public bool AutoUpdateCS2KZ
        {
            get => _settings.AutoUpdateCS2KZ;
            set { _settings.AutoUpdateCS2KZ = value; SaveSettings(); }
        }

        public float Scale
        {
            get => _settings.Scale;
            set { _settings.Scale = value; SaveSettings(); }
        }

        public bool ShowConsole
        {
            get => _settings.ShowConsole;
            set { _settings.ShowConsole = value; SaveSettings(); }
        }
    }

    public class Settings
    {
        public string Theme { get; set; } = "dracula";
        public Point WindowPosition { get; set; } = new Point(-1, -1);
        public bool CompactMode { get; set; } = false;
        public int GridColumns { get; set; } = 3;
        public float WindowOpacity { get; set; } = 1.0f;
        public bool AlwaysOnTop { get; set; } = false;
        
        public Dictionary<string, bool> ButtonVisibility { get; set; } = new Dictionary<string, bool>
        {
            ["dedicated_server"] = false,
            ["insecure"] = false,
            ["listen"] = true,
            ["mapping"] = true,
            ["source2viewer"] = true,
            ["cs2importer"] = true,
            ["skyboxconverter"] = false,
            ["vtf2png"] = false,
            ["loading_screen"] = true,
            ["point_worldtext"] = false,
            ["sounds"] = true
        };

        public List<string> ButtonOrder { get; set; } = new List<string>
        {
            "mapping", "listen", "dedicated_server", "insecure", "source2viewer",
            "cs2importer", "skyboxconverter", "loading_screen", "point_worldtext",
            "vtf2png", "sounds"
        };

        public bool AutoUpdateSource2Viewer { get; set; } = true;
        public bool AutoUpdateMetamod { get; set; } = true;
        public bool AutoUpdateCS2KZ { get; set; } = true;
        public float Scale { get; set; } = 1.0f;
        public bool ShowConsole { get; set; } = false;
    }
}
