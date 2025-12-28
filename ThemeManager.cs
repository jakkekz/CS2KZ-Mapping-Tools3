using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using Newtonsoft.Json;

namespace CS2KZMappingTools
{
    public class ThemeManager
    {
        private static ThemeManager? _instance;
        public static ThemeManager Instance => _instance ??= new ThemeManager();

        public Dictionary<string, Theme> Themes { get; private set; }
        public string CurrentTheme { get; set; } = "grey";

        private ThemeManager()
        {
            Themes = new Dictionary<string, Theme>
            {
                ["grey"] = new Theme
                {
                    WindowBackground = Color.FromArgb(26, 26, 26),
                    TitleBarBackground = Color.FromArgb(41, 41, 41),
                    ButtonBackground = Color.FromArgb(74, 74, 74),
                    ButtonHover = Color.FromArgb(89, 89, 89),
                    ButtonActive = Color.FromArgb(102, 102, 102),
                    Border = Color.FromArgb(102, 102, 102),
                    Text = Color.White,
                    AccentColor = Color.FromArgb(0, 120, 215)
                },
                ["black"] = new Theme
                {
                    WindowBackground = Color.Black,
                    TitleBarBackground = Color.FromArgb(13, 13, 13),
                    ButtonBackground = Color.FromArgb(38, 38, 38),
                    ButtonHover = Color.FromArgb(51, 51, 51),
                    ButtonActive = Color.FromArgb(64, 64, 64),
                    Border = Color.FromArgb(77, 77, 77),
                    Text = Color.White,
                    AccentColor = Color.FromArgb(0, 120, 215)
                },
                ["white"] = new Theme
                {
                    WindowBackground = Color.FromArgb(240, 240, 240),
                    TitleBarBackground = Color.FromArgb(224, 224, 224),
                    ButtonBackground = Color.FromArgb(191, 191, 191),
                    ButtonHover = Color.FromArgb(179, 179, 179),
                    ButtonActive = Color.FromArgb(166, 166, 166),
                    Border = Color.FromArgb(153, 153, 153),
                    Text = Color.FromArgb(26, 26, 26),
                    AccentColor = Color.FromArgb(0, 120, 215)
                },
                ["pink"] = new Theme
                {
                    WindowBackground = Color.FromArgb(64, 31, 46),
                    TitleBarBackground = Color.FromArgb(77, 38, 56),
                    ButtonBackground = Color.FromArgb(140, 64, 102),
                    ButtonHover = Color.FromArgb(166, 77, 122),
                    ButtonActive = Color.FromArgb(191, 89, 140),
                    Border = Color.FromArgb(204, 102, 153),
                    Text = Color.FromArgb(255, 242, 250),
                    AccentColor = Color.FromArgb(255, 105, 180)
                },
                ["orange"] = new Theme
                {
                    WindowBackground = Color.FromArgb(64, 38, 20),
                    TitleBarBackground = Color.FromArgb(77, 46, 26),
                    ButtonBackground = Color.FromArgb(153, 89, 38),
                    ButtonHover = Color.FromArgb(179, 102, 46),
                    ButtonActive = Color.FromArgb(204, 115, 51),
                    Border = Color.FromArgb(217, 128, 64),
                    Text = Color.FromArgb(255, 250, 242),
                    AccentColor = Color.FromArgb(255, 140, 0)
                },
                ["blue"] = new Theme
                {
                    WindowBackground = Color.FromArgb(20, 31, 64),
                    TitleBarBackground = Color.FromArgb(26, 38, 77),
                    ButtonBackground = Color.FromArgb(51, 77, 153),
                    ButtonHover = Color.FromArgb(64, 89, 179),
                    ButtonActive = Color.FromArgb(77, 102, 204),
                    Border = Color.FromArgb(89, 115, 217),
                    Text = Color.FromArgb(242, 250, 255),
                    AccentColor = Color.FromArgb(0, 120, 215)
                },
                ["red"] = new Theme
                {
                    WindowBackground = Color.FromArgb(64, 20, 20),
                    TitleBarBackground = Color.FromArgb(77, 26, 26),
                    ButtonBackground = Color.FromArgb(153, 51, 51),
                    ButtonHover = Color.FromArgb(179, 64, 64),
                    ButtonActive = Color.FromArgb(204, 77, 77),
                    Border = Color.FromArgb(217, 89, 89),
                    Text = Color.FromArgb(255, 242, 242),
                    AccentColor = Color.FromArgb(220, 53, 69)
                },
                ["green"] = new Theme
                {
                    WindowBackground = Color.FromArgb(20, 46, 20),
                    TitleBarBackground = Color.FromArgb(26, 56, 26),
                    ButtonBackground = Color.FromArgb(51, 128, 51),
                    ButtonHover = Color.FromArgb(64, 153, 64),
                    ButtonActive = Color.FromArgb(77, 179, 77),
                    Border = Color.FromArgb(89, 191, 89),
                    Text = Color.FromArgb(242, 255, 242),
                    AccentColor = Color.FromArgb(40, 167, 69)
                },
                ["yellow"] = new Theme
                {
                    WindowBackground = Color.FromArgb(128, 128, 0),
                    TitleBarBackground = Color.FromArgb(128, 128, 0),
                    ButtonBackground = Color.FromArgb(153, 140, 38),
                    ButtonHover = Color.FromArgb(179, 166, 51),
                    ButtonActive = Color.FromArgb(204, 191, 64),
                    Border = Color.FromArgb(217, 204, 77),
                    Text = Color.FromArgb(255, 255, 230),
                    AccentColor = Color.FromArgb(255, 193, 7)
                },
                ["dracula"] = new Theme
                {
                    WindowBackground = Color.FromArgb(40, 42, 54),
                    TitleBarBackground = Color.FromArgb(44, 47, 60),
                    ButtonBackground = Color.FromArgb(68, 71, 90),
                    ButtonHover = Color.FromArgb(129, 121, 179),
                    ButtonActive = Color.FromArgb(97, 88, 148),
                    Border = Color.FromArgb(97, 101, 124),
                    Text = Color.FromArgb(248, 248, 242),
                    AccentColor = Color.FromArgb(189, 147, 249)
                }
            };
        }

        public Theme GetCurrentTheme()
        {
            return Themes.ContainsKey(CurrentTheme) ? Themes[CurrentTheme] : Themes["grey"];
        }
    }

    public class Theme
    {
        public Color WindowBackground { get; set; }
        public Color TitleBarBackground { get; set; }
        public Color ButtonBackground { get; set; }
        public Color ButtonHover { get; set; }
        public Color ButtonActive { get; set; }
        public Color Border { get; set; }
        public Color Text { get; set; }
        public Color AccentColor { get; set; }
    }
}
