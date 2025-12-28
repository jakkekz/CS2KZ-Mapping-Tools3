using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    public class CustomColorTable : ProfessionalColorTable
    {
        private readonly Theme _theme;

        public CustomColorTable(Theme theme)
        {
            _theme = theme;
        }

        public override Color MenuItemSelected => _theme.ButtonHover;
        public override Color MenuItemBorder => Color.Transparent;
        public override Color MenuBorder => _theme.Border;
        public override Color MenuItemPressedGradientBegin => _theme.ButtonActive;
        public override Color MenuItemPressedGradientEnd => _theme.ButtonActive;
        public override Color MenuItemSelectedGradientBegin => _theme.ButtonHover;
        public override Color MenuItemSelectedGradientEnd => _theme.ButtonHover;
        public override Color ImageMarginGradientBegin => _theme.WindowBackground;
        public override Color ImageMarginGradientMiddle => _theme.WindowBackground;
        public override Color ImageMarginGradientEnd => _theme.WindowBackground;
        public override Color ToolStripDropDownBackground => _theme.WindowBackground;
        public override Color SeparatorDark => _theme.Border;
        public override Color SeparatorLight => _theme.Border;
        public override Color CheckBackground => _theme.WindowBackground;
        public override Color CheckSelectedBackground => _theme.ButtonHover;
        public override Color CheckPressedBackground => _theme.ButtonActive;
        public override Color ButtonSelectedBorder => Color.Transparent;
        public override Color ButtonPressedBorder => Color.Transparent;
        public override Color ButtonCheckedGradientBegin => _theme.WindowBackground;
        public override Color ButtonCheckedGradientMiddle => _theme.WindowBackground;
        public override Color ButtonCheckedGradientEnd => _theme.WindowBackground;
    }

    public partial class MainForm : Form
    {
        // Windows API for custom title bar
        private const int WM_NCHITTEST = 0x84;
        private const int WM_NCLBUTTONDOWN = 0xA1;
        private const int HTCAPTION = 0x2;
        private const int HTCLIENT = 0x1;
        private const int HTCLOSE = 20;
        private const int HTMINBUTTON = 8;

        [DllImport("user32.dll")]
        private static extern bool ReleaseCapture();

        [DllImport("user32.dll")]
        private static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);

        [DllImport("user32.dll")]
        private static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

        private static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
        private static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
        private const uint SWP_NOMOVE = 0x0002;
        private const uint SWP_NOSIZE = 0x0001;

        private readonly ThemeManager _themeManager;
        private readonly SettingsManager _settings;
        private readonly Dictionary<string, Image> _icons = new Dictionary<string, Image>();
        private readonly Dictionary<string, CustomButton> _buttons = new Dictionary<string, CustomButton>();
        private readonly ToolTip _toolTip = new ToolTip();
        private bool _updateAvailable = false;
        private MetamodUpdater? _metamodUpdater;
        private System.Windows.Forms.Timer? _updateCheckTimer;
        private int _updateCheckCount = 0; // Counter for local version checks
        private readonly MappingManager _mappingManager;
        private readonly ListenManager _listenManager;
        private readonly DedicatedManager _dedicatedManager;
        private readonly InsecureManager _insecureManager;
        private readonly PointWorldTextManager _pointWorldTextManager;
        
        // Console logging
        private RichTextBox? _consoleTextBox;
        private Panel? _consolePanel;
        private Label? _consoleLabel;
        private Button? _consoleClearButton;
        private Button? _consoleCopyButton;
        
        // Cached status indicators
        private bool _metamodButtonsHaveUpdate = false;
        private bool _metamodButtonsUpToDate = false;
        private bool _metamodButtonsNotInstalled = false;
        private bool _s2vHasUpdate = false;
        private bool _s2vUpToDate = false;
        private bool _s2vNotInstalled = false;
        
        // Drag-and-drop state
        private CustomButton? _draggingButton;
        private Point _dragStartPoint;
        private bool _isDraggingButton;
        private Point _originalButtonLocation;
        private bool _dropSuccessful;
        
        private Point _mouseDownPoint;
        private bool _isDragging;
        private Rectangle _closeButtonRect;
        private Rectangle _minimizeButtonRect;
        private Rectangle _updateButtonRect;
        private Rectangle _settingsButtonRect;
        private Rectangle _viewButtonRect;
        private Rectangle _linksButtonRect;
        private Rectangle _aboutButtonRect;
        private bool _closeButtonHover;
        private bool _minimizeButtonHover;
        private bool _updateButtonHover;
        private bool _settingsButtonHover;
        private bool _viewButtonHover;
        private bool _linksButtonHover;
        private bool _aboutButtonHover;
        
        private const int TitleBarHeight = 30;
        private const int MenuBarHeight = 28;
        private const int ButtonWidth = 100;
        private const int ButtonHeight = 100;
        private const int ButtonSpacing = 7;
        private new const int Padding = 14;
        
        // Drag visual feedback
        private Bitmap? _dragButtonImage;
        private Point _dragButtonLocation;
        private Point _prevDragButtonLocation;
        private System.Windows.Forms.Timer? _processCheckTimer;

        public MainForm()
        {
            InitializeComponent();
            
            _themeManager = ThemeManager.Instance;
            _settings = SettingsManager.Instance;
            _mappingManager = new MappingManager();
            _listenManager = new ListenManager();
            _dedicatedManager = new DedicatedManager();
            _insecureManager = new InsecureManager();
            _pointWorldTextManager = new PointWorldTextManager();
            
            // Set form properties
            this.FormBorderStyle = FormBorderStyle.None;
            this.StartPosition = FormStartPosition.Manual;
            this.DoubleBuffered = true;
            this.Font = new Font("Roboto", 15F, FontStyle.Regular);
            this.Text = "CS2KZ Mapping Tools";
            this.AllowDrop = true;
            
            // Set theme
            _themeManager.CurrentTheme = _settings.Theme;
            
            // Load icons
            LoadIcons();
            
            // Create UI
            CreateTitleBar();
            CreateButtons();
            CreateConsole();
            
            // Setup tooltips
            SetupTooltips();
            
            // Apply theme
            ApplyTheme();
            
            // Load window position
            if (_settings.WindowPosition.X != -1)
            {
                this.Location = _settings.WindowPosition;
            }
            else
            {
                CenterToScreen();
            }
            
            // Set opacity
            this.Opacity = _settings.WindowOpacity;
            
            // Set always on top
            if (_settings.AlwaysOnTop)
            {
                SetAlwaysOnTop(true);
            }
            
            // Wire up events
            this.MouseDown += TitleBar_MouseDown;
            this.MouseMove += TitleBar_MouseMove;
            this.MouseUp += TitleBar_MouseUp;
            this.FormClosing += MainForm_FormClosing;
            this.Paint += MainForm_Paint;
            this.DragOver += MainForm_DragOver;
            this.DragDrop += MainForm_DragDrop;
            
            // Setup process check timer
            _processCheckTimer = new System.Windows.Forms.Timer();
            _processCheckTimer.Interval = 2000; // Check every 2 seconds
            _processCheckTimer.Tick += ProcessCheckTimer_Tick;
            _processCheckTimer.Start();
            
            // Setup Metamod update checker
            _metamodUpdater = new MetamodUpdater();
            _updateCheckTimer = new System.Windows.Forms.Timer();
            _updateCheckTimer.Interval = 10000; // Check local every 10 seconds, remote every 5 minutes
            _updateCheckTimer.Tick += UpdateCheckTimer_Tick;
            _updateCheckTimer.Start();
            
            // Do initial update check after form is shown
            this.Shown += async (s, e) =>
            {
                await CheckMetamodUpdatesAsync();
                await CheckSource2ViewerVersionAsync();
            };
        }

        private void InitializeComponent()
        {
            this.SuspendLayout();
            // 
            // MainForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(259, 400);
            this.Name = "MainForm";
            this.ResumeLayout(false);
        }

        private void LoadIcons()
        {
            string iconsPath = Path.Combine(ResourceExtractor.ExtractResources(), "icons");
            
            var iconFiles = new Dictionary<string, string>
            {
                ["dedicated_server"] = "icondedicated.ico",
                ["insecure"] = "iconinsecure.ico",
                ["listen"] = "iconlisten.ico",
                ["mapping"] = "hammerkz.ico",
                ["source2viewer"] = "source2viewer.ico",
                ["cs2importer"] = "porting.ico",
                ["skyboxconverter"] = "skybox.ico",
                ["vtf2png"] = "vtf2png.ico",
                ["loading_screen"] = "loading.ico",
                ["point_worldtext"] = "text.ico",
                ["sounds"] = "sounds.ico",
                ["title_icon"] = "hammerkz.ico",
                ["update_available"] = "update.ico",
                ["update_not_available"] = "updatenot.ico"
            };

            foreach (var kvp in iconFiles)
            {
                string path = Path.Combine(iconsPath, kvp.Value);
                if (File.Exists(path))
                {
                    try
                    {
                        _icons[kvp.Key] = Image.FromFile(path);
                    }
                    catch { }
                }
            }
            
            // Set form icon
            if (_icons.ContainsKey("title_icon"))
            {
                this.Icon = Icon.FromHandle(((Bitmap)_icons["title_icon"]).GetHicon());
            }
        }

        private void CreateTitleBar()
        {
            // Title bar is drawn manually in OnPaint
            // Button rectangles will be calculated there
        }

        private void CreateButtons()
        {
            // Clear existing buttons
            foreach (var button in _buttons.Values)
            {
                this.Controls.Remove(button);
                button.Dispose();
            }
            _buttons.Clear();
            
            int visibleCount = _settings.ButtonVisibility.Count(kvp => kvp.Value);
            int columns = _settings.GridColumns;
            int rows = (visibleCount + columns - 1) / columns;
            
            // Apply scale to all dimensions - use Math.Round for consistent rounding
            int scaledTitleBarHeight = (int)Math.Round(TitleBarHeight * _settings.Scale);
            int scaledMenuBarHeight = (int)Math.Round(MenuBarHeight * _settings.Scale);
            int scaledPadding = (int)Math.Round(Padding * _settings.Scale);
            
            // Make buttons larger in 1 column mode, then apply scale
            float baseWidth = columns == 1 ? 110 : ButtonWidth;
            float baseHeight = columns == 1 ? 110 : ButtonHeight;
            int buttonWidth = (int)Math.Round(baseWidth * _settings.Scale);
            int buttonHeight = (int)Math.Round(baseHeight * _settings.Scale);
            int buttonSpacing = (int)Math.Round(ButtonSpacing * _settings.Scale);
            
            int x = scaledPadding;
            int y = scaledTitleBarHeight + scaledMenuBarHeight + scaledPadding;
            int col = 0;

            var buttonConfig = new Dictionary<string, (string label, string tooltip)>
            {
                ["mapping"] = ("Mapping", "Launches CS2 Hammer Editor with latest Metamod, CS2KZ and Mapping API versions"),
                ["listen"] = ("Listen", "Launches CS2 with latest Metamod and CS2KZ versions"),
                ["fix_cs2"] = ("Fix CS2", "Restores original gameinfo files if CS2 won't start"),
                ["dedicated_server"] = ("Dedicated\nServer", "Launches CS2 Dedicated Server with latest versions"),
                ["insecure"] = ("Insecure", "Launches CS2 in insecure mode"),
                ["source2viewer"] = ("Source2\nViewer", "Launches Source2Viewer with latest dev build"),
                ["cs2importer"] = ("CS2\nImporter", "Port CS:GO maps to CS2"),
                ["skyboxconverter"] = ("Skybox\nConverter", "Convert cubemap skyboxes to CS2 format"),
                ["loading_screen"] = ("Loading\nScreen", "Add loading screen images and map info"),
                ["point_worldtext"] = ("Point\nWorldtext", "Create CS:GO style point_worldtext images"),
                ["vtf2png"] = ("VTF to\nPNG", "Convert CS:GO VTF files to PNG"),
                ["sounds"] = ("Sounds", "Make adding custom sounds easier")
            };

            foreach (var buttonId in _settings.ButtonOrder)
            {
                if (!_settings.ButtonVisibility.ContainsKey(buttonId) || !_settings.ButtonVisibility[buttonId])
                    continue;

                // Skip if button already exists
                if (_buttons.ContainsKey(buttonId))
                    continue;

                if (!buttonConfig.ContainsKey(buttonId))
                    continue;

                var config = buttonConfig[buttonId];
                var iconPath = Path.Combine(ResourceExtractor.ExtractResources(), "icons", GetIconFileName(buttonId));
                
                var button = new CustomButton(this)
                {
                    Location = new Point(x, y),
                    Size = new Size(buttonWidth, buttonHeight),
                    Text = config.label,
                    Tag = buttonId,
                    IconPath = iconPath,
                    ToolTipText = config.tooltip
                };
                button.SetScale(_settings.Scale);
                button.SetCompactMode(true);

                button.Click += Button_Click;
                button.MouseDown += Button_MouseDown;
                button.MouseMove += Button_MouseMove;
                button.MouseUp += Button_MouseUp;
                button.AllowDrop = true;
                button.DragOver += Button_DragOver;
                button.DragDrop += Button_DragDrop;
                button.QueryContinueDrag += Button_QueryContinueDrag;
                button.GiveFeedback += Button_GiveFeedback;
                
                this.Controls.Add(button);
                _buttons[buttonId] = button;
                
                // Always register tooltip text (will be enabled/disabled by UpdateButtonTooltips)
                if (!string.IsNullOrEmpty(config.tooltip))
                {
                    _toolTip.SetToolTip(button, config.tooltip);
                }

                col++;
                if (col >= columns)
                {
                    col = 0;
                    x = scaledPadding;
                    y += buttonHeight + buttonSpacing;
                }
                else
                {
                    x += buttonWidth + buttonSpacing;
                }
            }
            
            // Calculate form size based on actual button positions
            // Update form size with new button layout
            UpdateFormSize();
        }
        
        private void ApplyStatusIndicators()
        {
            // Apply cached status to metamod buttons
            string[] metamodButtons = { "mapping", "listen", "dedicated_server", "insecure" };
            foreach (var buttonId in metamodButtons)
            {
                if (_buttons.ContainsKey(buttonId))
                {
                    if (_metamodButtonsNotInstalled)
                        _buttons[buttonId].SetNotInstalled(true);
                    else if (_metamodButtonsHaveUpdate)
                        _buttons[buttonId].SetUpdateAvailable(true);
                    else if (_metamodButtonsUpToDate)
                        _buttons[buttonId].SetUpToDate(true);
                    else
                        _buttons[buttonId].ClearStatusIndicator();
                }
            }
            
            // Apply cached status to S2V button
            if (_buttons.ContainsKey("source2viewer"))
            {
                if (_s2vNotInstalled)
                    _buttons["source2viewer"].SetNotInstalled(true);
                else if (_s2vHasUpdate)
                    _buttons["source2viewer"].SetUpdateAvailable(true);
                else if (_s2vUpToDate)
                    _buttons["source2viewer"].SetUpToDate(true);
                else
                    _buttons["source2viewer"].ClearStatusIndicator();
            }
        }
        
        private void CreateConsole()
        {
            // Create console panel
            _consolePanel = new Panel
            {
                Height = (int)(150 * _settings.Scale),
                Dock = DockStyle.Bottom,
                Visible = _settings.ShowConsole,
                BackColor = _themeManager.GetCurrentTheme().WindowBackground,
                BorderStyle = BorderStyle.None
            };
            
            // Create console label
            _consoleLabel = new Label
            {
                Text = "Console Log",
                Height = (int)(25 * _settings.Scale),
                Dock = DockStyle.Top,
                ForeColor = _themeManager.GetCurrentTheme().Text,
                BackColor = _themeManager.GetCurrentTheme().WindowBackground,
                Font = new Font("Consolas", 9F, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding((int)(5 * _settings.Scale), 0, 0, 0)
            };
            
            // Create copy all button
            _consoleCopyButton = new Button
            {
                Text = "Copy All",
                Width = (int)(65 * _settings.Scale),
                Height = (int)(20 * _settings.Scale),
                Anchor = AnchorStyles.Top | AnchorStyles.Left,
                Location = new Point((int)(100 * _settings.Scale), (int)(2 * _settings.Scale)),
                FlatStyle = FlatStyle.Flat,
                TabStop = false,
                Cursor = Cursors.Hand,
                Font = new Font("Segoe UI", 8.0F, FontStyle.Regular)
            };
            _consoleCopyButton.FlatAppearance.BorderSize = 0;
            _consoleCopyButton.Click += (s, e) => CopyAllConsoleText();

            // Create clear button with text
            _consoleClearButton = new Button
            {
                Text = "Clear",
                Width = (int)(50 * _settings.Scale),
                Height = (int)(20 * _settings.Scale),
                Anchor = AnchorStyles.Top | AnchorStyles.Left,
                Location = new Point((int)(170 * _settings.Scale), (int)(2 * _settings.Scale)),
                FlatStyle = FlatStyle.Flat,
                TabStop = false,
                Cursor = Cursors.Hand,
                Font = new Font("Segoe UI", 8.0F, FontStyle.Regular)
            };
            _consoleClearButton.FlatAppearance.BorderSize = 0;
            _consoleClearButton.Click += (s, e) => ClearConsole();
            
            // Create console text box
            _consoleTextBox = new RichTextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = RichTextBoxScrollBars.Both,
                Dock = DockStyle.Fill,
                BackColor = _themeManager.GetCurrentTheme().WindowBackground,
                ForeColor = _themeManager.GetCurrentTheme().Text,
                BorderStyle = BorderStyle.None,
                Font = new Font("Consolas", 8F, FontStyle.Regular),
                Margin = new Padding((int)(5 * _settings.Scale))
            };
            
            // Add controls to console panel
            _consolePanel.Controls.Add(_consoleTextBox);
            _consolePanel.Controls.Add(_consoleLabel);
            _consolePanel.Controls.Add(_consoleCopyButton);
            _consolePanel.Controls.Add(_consoleClearButton);
            _consoleCopyButton.BringToFront();
            _consoleClearButton.BringToFront();
            
            // Add console panel to form
            this.Controls.Add(_consolePanel);
            
            // Subscribe to all logging events
            _mappingManager.LogEvent += OnLogMessage;
            _listenManager.LogEvent += OnLogMessage;
            _dedicatedManager.LogEvent += OnLogMessage;
            _insecureManager.LogEvent += OnLogMessage;
            _pointWorldTextManager.LogEvent += OnLogMessage;
            
            // Update form size to accommodate console
            UpdateFormSize();
            
            // Test console logging
            OnLogMessage("Console logging system initialized successfully!");
        }
        
        private void UpdateConsoleVisibility()
        {
            if (_consolePanel != null)
            {
                _consolePanel.Visible = _settings.ShowConsole;
                UpdateFormSize();
            }
        }
        
        private void OnLogMessage(string message)
        {
            if (_consoleTextBox == null) return;
            
            // Ensure we're on the UI thread
            if (_consoleTextBox.InvokeRequired)
            {
                _consoleTextBox.Invoke(new Action<string>(OnLogMessage), message);
                return;
            }
            
            string timestamp = DateTime.Now.ToString("HH:mm:ss");
            string logLine = $"[{timestamp}] {message}";
            
            // Determine text color based on message content
            Color textColor = Color.White; // Default color
            
            if (message.StartsWith("Warning:") || message.Contains("Warning:"))
            {
                textColor = Color.Yellow;
            }
            else if (message.StartsWith("✗") || message.Contains("Error") || message.Contains("Failed") || message.Contains("error"))
            {
                textColor = Color.Red;
            }
            
            // Add colored text to RichTextBox
            _consoleTextBox.SelectionStart = _consoleTextBox.TextLength;
            _consoleTextBox.SelectionLength = 0;
            _consoleTextBox.SelectionColor = textColor;
            _consoleTextBox.AppendText(logLine + Environment.NewLine);
            _consoleTextBox.SelectionColor = Color.White; // Reset to default
            _consoleTextBox.ScrollToCaret();
            
            // Limit console lines to prevent memory issues
            var lines = _consoleTextBox.Lines;
            if (lines.Length > 1000)
            {
                var newLines = lines.Skip(lines.Length - 800).ToArray();
                _consoleTextBox.Lines = newLines;
            }
        }
        
        private void ClearConsole()
        {
            if (_consoleTextBox != null)
            {
                _consoleTextBox.Clear();
            }
        }
        
        private void CopyAllConsoleText()
        {
            if (_consoleTextBox != null && !string.IsNullOrEmpty(_consoleTextBox.Text))
            {
                try
                {
                    Clipboard.SetText(_consoleTextBox.Text);
                    OnLogMessage("Console text copied to clipboard");
                }
                catch (Exception ex)
                {
                    OnLogMessage($"Failed to copy text to clipboard: {ex.Message}");
                }
            }
            else
            {
                OnLogMessage("No console text to copy");
            }
        }
        
        private void DrawClearIcon(object? sender, PaintEventArgs e)
        {
            if (sender is not Button button) return;
            
            var theme = _themeManager.GetCurrentTheme();
            var iconColor = theme.Text; // Use theme text color for the icon
            
            // Create pen for drawing the X
            using (var pen = new Pen(iconColor, 2.0f))
            {
                // Calculate the center and size for the X
                int centerX = button.Width / 2;
                int centerY = button.Height / 2;
                int size = (int)Math.Min(button.Width * 0.4, button.Height * 0.4);
                
                // Draw X (two diagonal lines)
                e.Graphics.DrawLine(pen, 
                    centerX - size/2, centerY - size/2, 
                    centerX + size/2, centerY + size/2);
                e.Graphics.DrawLine(pen, 
                    centerX + size/2, centerY - size/2, 
                    centerX - size/2, centerY + size/2);
            }
        }
        
        private void UpdateFormSize()
        {
            if (this.Controls.OfType<CustomButton>().Any())
            {
                int maxX = this.Controls.OfType<CustomButton>().Max(b => b.Right);
                int maxY = this.Controls.OfType<CustomButton>().Max(b => b.Bottom);
                
                // Apply scale to padding
                int scaledPadding = (int)Math.Round(Padding * _settings.Scale);
                
                // Add extra width for 1 column mode to fit everything better
                int extraWidth = (_settings.GridColumns == 1) ? 2 : 0;
                int formWidth = maxX + scaledPadding + extraWidth;
                int formHeight = maxY + scaledPadding;
                
                // Add console height if visible
                if (_settings.ShowConsole && _consolePanel != null)
                {
                    formHeight += _consolePanel.Height;
                }
                
                this.ClientSize = new Size(formWidth, formHeight);
                
                // Reapply cached status indicators
                ApplyStatusIndicators();
            }
        }

        private void SetupTooltips()
        {
            // Configure tooltip
            _toolTip.InitialDelay = 500;
            _toolTip.ReshowDelay = 100;
            _toolTip.AutoPopDelay = 5000;
            _toolTip.ShowAlways = true;
            _toolTip.Active = true;
            
            // Note: Tooltips for title bar buttons are shown manually in MouseMove event
            // because they are drawn manually and not actual controls
        }

        private string GetIconFileName(string buttonId)
        {
            var iconMap = new Dictionary<string, string>
            {
                ["mapping"] = "hammerkz.ico",
                ["listen"] = "iconlisten.ico",
                ["dedicated_server"] = "icondedicated.ico",
                ["insecure"] = "iconinsecure.ico",
                ["source2viewer"] = "source2viewer.ico",
                ["cs2importer"] = "porting.ico",
                ["skyboxconverter"] = "skybox.ico",
                ["loading_screen"] = "loading.ico",
                ["point_worldtext"] = "text.ico",
                ["vtf2png"] = "vtf2png.ico",
                ["sounds"] = "sounds.ico"
            };
            
            return iconMap.ContainsKey(buttonId) ? iconMap[buttonId] : "hammerkz.ico";
        }

        private void ApplyTheme()
        {
            var theme = _themeManager.GetCurrentTheme();
            this.BackColor = theme.WindowBackground;
            this.ForeColor = theme.Text;
            
            foreach (var button in _buttons.Values)
            {
                button.ApplyTheme(theme);
            }
            
            // Apply theme to console controls
            if (_consolePanel != null)
            {
                _consolePanel.BackColor = theme.WindowBackground;
                if (_consoleLabel != null)
                {
                    _consoleLabel.ForeColor = theme.Text;
                    _consoleLabel.BackColor = theme.WindowBackground;
                }
                if (_consoleTextBox != null)
                {
                    _consoleTextBox.BackColor = theme.WindowBackground;
                    _consoleTextBox.ForeColor = theme.Text;
                }
                // Apply theme to console copy button
                if (_consoleCopyButton != null)
                {
                    _consoleCopyButton.BackColor = theme.ButtonBackground;
                    _consoleCopyButton.ForeColor = theme.Text;
                    _consoleCopyButton.FlatAppearance.MouseOverBackColor = theme.ButtonHover;
                    _consoleCopyButton.FlatAppearance.MouseDownBackColor = theme.ButtonActive;
                }
                
                // Apply theme to console clear button
                if (_consoleClearButton != null)
                {
                    _consoleClearButton.BackColor = theme.ButtonBackground;
                    _consoleClearButton.ForeColor = theme.Text;
                    _consoleClearButton.FlatAppearance.MouseOverBackColor = theme.ButtonHover;
                    _consoleClearButton.FlatAppearance.MouseDownBackColor = theme.ButtonActive;
                }
            }
            
            this.Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            
            var theme = _themeManager.GetCurrentTheme();
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            
            // Apply scale to all dimensions
            int scaledTitleBarHeight = (int)(TitleBarHeight * _settings.Scale);
            int scaledMenuBarHeight = (int)(MenuBarHeight * _settings.Scale);
            float scaledFontSize = 9F * _settings.Scale;
            int scaledIconSize = (int)(16 * _settings.Scale);
            int scaledIconX = (int)(8 * _settings.Scale);
            int scaledIconSpacing = (int)(20 * _settings.Scale);
            
            // Draw title bar background
            using (var brush = new SolidBrush(theme.TitleBarBackground))
            {
                g.FillRectangle(brush, 0, 0, this.ClientSize.Width, scaledTitleBarHeight);
            }
            
            // Draw title bar border
            using (var pen = new Pen(theme.Border, 1))
            {
                g.DrawLine(pen, 0, scaledTitleBarHeight, this.ClientSize.Width, scaledTitleBarHeight);
            }
            
            // Draw icon and title
            int iconX = scaledIconX;
            if (_icons.ContainsKey("title_icon"))
            {
                g.DrawImage(_icons["title_icon"], iconX, (scaledTitleBarHeight - scaledIconSize) / 2, scaledIconSize, scaledIconSize);
                iconX += scaledIconSpacing;
            }
            
            // Only draw title text when using 2+ columns
            if (_settings.GridColumns >= 2)
            {
                string titleText = _settings.GridColumns == 2 ? "CS2KZ MTools" : "CS2KZ Mapping Tools";
                using (var brush = new SolidBrush(theme.Text))
                using (var font = new Font("Roboto", scaledFontSize))
                {
                    g.DrawString(titleText, font, brush, iconX, (scaledTitleBarHeight - (int)(15 * _settings.Scale)) / 2);
                }
            }
            
            // Calculate button positions in title bar: Settings, Update, Minimize, Close
            int buttonSize = (int)(25 * _settings.Scale);
            int buttonY = (scaledTitleBarHeight - buttonSize) / 2;
            int buttonSpacing1 = (int)(15 * _settings.Scale);
            int buttonSpacing2 = (int)(10 * _settings.Scale);
            int buttonSpacing3 = (int)(5 * _settings.Scale);
            _settingsButtonRect = new Rectangle(this.ClientSize.Width - buttonSize * 4 - buttonSpacing1, buttonY, buttonSize, buttonSize);
            _updateButtonRect = new Rectangle(this.ClientSize.Width - buttonSize * 3 - buttonSpacing2, buttonY, buttonSize, buttonSize);
            _minimizeButtonRect = new Rectangle(this.ClientSize.Width - buttonSize * 2 - buttonSpacing3, buttonY, buttonSize, buttonSize);
            _closeButtonRect = new Rectangle(this.ClientSize.Width - buttonSize - buttonSpacing3, buttonY, buttonSize, buttonSize);
            
            // Draw settings button (three sliders icon)
            using (var brush = new SolidBrush(_settingsButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _settingsButtonRect);
            }
            using (var pen = new Pen(theme.Text, 1.5f * _settings.Scale))
            {
                int centerX = _settingsButtonRect.X + _settingsButtonRect.Width / 2;
                int centerY = _settingsButtonRect.Y + _settingsButtonRect.Height / 2;
                int sliderWidth = (int)(5 * _settings.Scale);
                int sliderSpacing = (int)(4 * _settings.Scale);
                int knobWidth = (int)(2 * _settings.Scale);
                int knobHeight = (int)(3 * _settings.Scale);
                
                // Top slider line and knob
                g.DrawLine(pen, centerX - sliderWidth, centerY - sliderSpacing, centerX + sliderWidth, centerY - sliderSpacing);
                g.FillRectangle(new SolidBrush(theme.Text), centerX - (int)(3 * _settings.Scale), centerY - sliderSpacing - knobHeight, knobWidth, knobHeight);
                
                // Middle slider line and knob
                g.DrawLine(pen, centerX - sliderWidth, centerY, centerX + sliderWidth, centerY);
                g.FillRectangle(new SolidBrush(theme.Text), centerX + (int)(2 * _settings.Scale), centerY - (int)(1 * _settings.Scale), knobWidth, knobHeight);
                
                // Bottom slider line and knob
                g.DrawLine(pen, centerX - sliderWidth, centerY + sliderSpacing, centerX + sliderWidth, centerY + sliderSpacing);
                g.FillRectangle(new SolidBrush(theme.Text), centerX - (int)(1 * _settings.Scale), centerY + sliderSpacing, knobWidth, knobHeight);
            }
            
            // Draw update button with appropriate icon
            using (var brush = new SolidBrush(_updateButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _updateButtonRect);
            }
            
            // Draw update icon
            string updateIconKey = _updateAvailable ? "update_available" : "update_not_available";
            if (_icons.ContainsKey(updateIconKey))
            {
                int iconSize = (int)(16 * _settings.Scale);
                int updateIconX = _updateButtonRect.X + (_updateButtonRect.Width - iconSize) / 2;
                int updateIconY = _updateButtonRect.Y + (_updateButtonRect.Height - iconSize) / 2;
                
                // Apply color matrix to match theme
                using (var imageAttr = new System.Drawing.Imaging.ImageAttributes())
                {
                    var colorMatrix = new System.Drawing.Imaging.ColorMatrix(
                        new float[][] 
                        {
                            new float[] {0, 0, 0, 0, 0},
                            new float[] {0, 0, 0, 0, 0},
                            new float[] {0, 0, 0, 0, 0},
                            new float[] {0, 0, 0, 1, 0},
                            new float[] {theme.Text.R / 255f, theme.Text.G / 255f, theme.Text.B / 255f, 0, 1}
                        });
                    imageAttr.SetColorMatrix(colorMatrix);
                    g.DrawImage(_icons[updateIconKey], 
                        new Rectangle(updateIconX, updateIconY, iconSize, iconSize),
                        0, 0, _icons[updateIconKey].Width, _icons[updateIconKey].Height,
                        GraphicsUnit.Pixel, imageAttr);
                }
            }
            
            // Draw minimize button
            using (var brush = new SolidBrush(_minimizeButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _minimizeButtonRect);
            }
            using (var pen = new Pen(theme.Text, 2 * _settings.Scale))
            {
                int minLineY = _minimizeButtonRect.Top + _minimizeButtonRect.Height / 2;
                int minMargin = (int)(7 * _settings.Scale);
                g.DrawLine(pen, 
                    _minimizeButtonRect.Left + minMargin, minLineY,
                    _minimizeButtonRect.Right - minMargin, minLineY);
            }
            
            // Draw close button
            using (var brush = new SolidBrush(_closeButtonHover ? Color.FromArgb(232, 17, 35) : Color.Transparent))
            {
                g.FillRectangle(brush, _closeButtonRect);
            }
            using (var pen = new Pen(theme.Text, 2 * _settings.Scale))
            {
                int closeMargin = (int)(7 * _settings.Scale);
                g.DrawLine(pen,
                    _closeButtonRect.Left + closeMargin, _closeButtonRect.Top + closeMargin,
                    _closeButtonRect.Right - closeMargin, _closeButtonRect.Bottom - closeMargin);
                g.DrawLine(pen,
                    _closeButtonRect.Right - closeMargin, _closeButtonRect.Top + closeMargin,
                    _closeButtonRect.Left + closeMargin, _closeButtonRect.Bottom - closeMargin);
            }
            
            // Draw menu bar
            using (var brush = new SolidBrush(theme.TitleBarBackground))
            {
                g.FillRectangle(brush, 0, scaledTitleBarHeight, this.ClientSize.Width, scaledMenuBarHeight);
            }
            using (var pen = new Pen(theme.Border, 1))
            {
                g.DrawLine(pen, 0, scaledTitleBarHeight + scaledMenuBarHeight, this.ClientSize.Width, scaledTitleBarHeight + scaledMenuBarHeight);
            }
            
            // Calculate menu item positions
            int menuX = (int)(10 * _settings.Scale);
            int menuY = scaledTitleBarHeight + (int)(5 * _settings.Scale);
            int menuItemSpacing = (int)(38 * _settings.Scale);  // Reduced from 45 for less spacing
            int menuWidth = (int)(35 * _settings.Scale);  // Reduced from 40 for tighter fit
            int menuHeight = scaledMenuBarHeight - (int)(10 * _settings.Scale);
            
            // About on the right side
            int aboutX = this.ClientSize.Width - (int)(55 * _settings.Scale);  // Adjusted for smaller width
            int aboutWidth = (int)(45 * _settings.Scale);  // Reduced from 50
            
            _viewButtonRect = new Rectangle(menuX, menuY, menuWidth, menuHeight);
            _linksButtonRect = new Rectangle(menuX + menuItemSpacing, menuY, menuWidth, menuHeight);
            _aboutButtonRect = new Rectangle(aboutX, menuY, aboutWidth, menuHeight);
            
            // Draw View menu item
            using (var brush = new SolidBrush(_viewButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _viewButtonRect);
            }
            using (var brush = new SolidBrush(theme.Text))
            using (var font = new Font("Roboto", scaledFontSize))
            {
                var textSize = g.MeasureString("View", font);
                float textX = _viewButtonRect.X + (_viewButtonRect.Width - textSize.Width) / 2;
                float textY = _viewButtonRect.Y + (int)(2 * _settings.Scale);
                g.DrawString("View", font, brush, textX, textY);
            }
            
            // Draw Links menu item
            using (var brush = new SolidBrush(_linksButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _linksButtonRect);
            }
            using (var brush = new SolidBrush(theme.Text))
            using (var font = new Font("Roboto", scaledFontSize))
            {
                var textSize = g.MeasureString("Links", font);
                float textX = _linksButtonRect.X + (_linksButtonRect.Width - textSize.Width) / 2;
                float textY = _linksButtonRect.Y + (int)(2 * _settings.Scale);
                g.DrawString("Links", font, brush, textX, textY);
            }
            
            // Draw About menu item
            using (var brush = new SolidBrush(_aboutButtonHover ? Color.FromArgb(60, Color.White) : Color.Transparent))
            {
                g.FillRectangle(brush, _aboutButtonRect);
            }
            using (var brush = new SolidBrush(theme.Text))
            using (var font = new Font("Roboto", scaledFontSize))
            {
                var textSize = g.MeasureString("About", font);
                float textX = _aboutButtonRect.X + (_aboutButtonRect.Width - textSize.Width) / 2;
                float textY = _aboutButtonRect.Y + (int)(2 * _settings.Scale);
                g.DrawString("About", font, brush, textX, textY);
            }
        }
        
        private void MainForm_Paint(object? sender, PaintEventArgs e)
        {
            // This is called after all child controls are painted
            // Draw dragging button following cursor on top of everything
            if (_isDraggingButton && _dragButtonImage != null)
            {
                var g = e.Graphics;
                g.SmoothingMode = SmoothingMode.AntiAlias;
                
                // Draw larger shadow for better visibility
                using (var shadowBrush = new SolidBrush(Color.FromArgb(150, 0, 0, 0)))
                {
                    g.FillRectangle(shadowBrush, 
                        _dragButtonLocation.X + 4, 
                        _dragButtonLocation.Y + 4, 
                        _dragButtonImage.Width, 
                        _dragButtonImage.Height);
                }
                
                // Draw semi-transparent button image with higher opacity
                var imageAttributes = new System.Drawing.Imaging.ImageAttributes();
                var colorMatrix = new System.Drawing.Imaging.ColorMatrix();
                colorMatrix.Matrix33 = 0.85f; // 85% opacity for better visibility
                imageAttributes.SetColorMatrix(colorMatrix);
                
                g.DrawImage(_dragButtonImage, 
                    new Rectangle(_dragButtonLocation, _dragButtonImage.Size),
                    0, 0, _dragButtonImage.Width, _dragButtonImage.Height,
                    GraphicsUnit.Pixel, imageAttributes);
            }
        }

        private void TitleBar_MouseDown(object? sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left && e.Y < TitleBarHeight)
            {
                if (_closeButtonRect.Contains(e.Location))
                {
                    this.Close();
                    return;
                }
                
                if (_minimizeButtonRect.Contains(e.Location))
                {
                    this.WindowState = FormWindowState.Minimized;
                    return;
                }
                
                if (_updateButtonRect.Contains(e.Location))
                {
                    CheckForUpdates();
                    return;
                }
                
                if (_settingsButtonRect.Contains(e.Location))
                {
                    ShowSettingsMenu();
                    return;
                }
                
                _isDragging = true;
                _mouseDownPoint = e.Location;
                return;
            }
            
            // Check menu bar clicks
            if (e.Button == MouseButtons.Left && e.Y >= TitleBarHeight && e.Y < TitleBarHeight + MenuBarHeight)
            {
                if (_viewButtonRect.Contains(e.Location))
                {
                    ShowViewMenu();
                    return;
                }
                
                if (_linksButtonRect.Contains(e.Location))
                {
                    ShowLinksMenu();
                    return;
                }
                
                if (_aboutButtonRect.Contains(e.Location))
                {
                    ShowAboutMenu();
                    return;
                }
            }
        }

        private void TitleBar_MouseMove(object? sender, MouseEventArgs e)
        {
            // Window dragging
            if (_isDragging)
            {
                Point currentScreenPos = PointToScreen(e.Location);
                Point newLocation = new Point(
                    currentScreenPos.X - _mouseDownPoint.X,
                    currentScreenPos.Y - _mouseDownPoint.Y);
                this.Location = newLocation;
            }
            
            // Update button hover states
            bool prevCloseHover = _closeButtonHover;
            bool prevMinimizeHover = _minimizeButtonHover;
            bool prevUpdateHover = _updateButtonHover;
            bool prevSettingsHover = _settingsButtonHover;
            bool prevViewHover = _viewButtonHover;
            bool prevLinksHover = _linksButtonHover;
            bool prevAboutHover = _aboutButtonHover;
            
            _closeButtonHover = _closeButtonRect.Contains(e.Location);
            _minimizeButtonHover = _minimizeButtonRect.Contains(e.Location);
            _updateButtonHover = _updateButtonRect.Contains(e.Location);
            _settingsButtonHover = _settingsButtonRect.Contains(e.Location) && e.Y < TitleBarHeight;
            _viewButtonHover = _viewButtonRect.Contains(e.Location);
            _linksButtonHover = _linksButtonRect.Contains(e.Location);
            _aboutButtonHover = _aboutButtonRect.Contains(e.Location);
            
            // Show tooltips for title bar buttons
            if (_closeButtonHover)
                _toolTip.Show("Close", this, e.X, e.Y - 25, 2000);
            else if (_minimizeButtonHover)
                _toolTip.Show("Minimize", this, e.X, e.Y - 25, 2000);
            else if (_updateButtonHover)
                _toolTip.Show("Check for updates", this, e.X, e.Y - 25, 2000);
            else if (_settingsButtonHover && e.Y < TitleBarHeight)
                _toolTip.Show("Settings", this, e.X, e.Y - 25, 2000);
            else if (!_viewButtonHover && !_linksButtonHover && !_aboutButtonHover)
                _toolTip.Hide(this);
            
            if (prevCloseHover != _closeButtonHover || prevMinimizeHover != _minimizeButtonHover || 
                prevUpdateHover != _updateButtonHover || prevSettingsHover != _settingsButtonHover ||
                prevViewHover != _viewButtonHover || prevLinksHover != _linksButtonHover ||
                prevAboutHover != _aboutButtonHover)
            {
                this.Invalidate(new Rectangle(0, 0, this.ClientSize.Width, TitleBarHeight + MenuBarHeight));
            }
            
            // Change cursor
            if (_closeButtonHover || _minimizeButtonHover || _updateButtonHover || _settingsButtonHover ||
                _viewButtonHover || _linksButtonHover || _aboutButtonHover)
            {
                this.Cursor = Cursors.Hand;
            }
            else if (_isDragging && e.Y < TitleBarHeight)
            {
                this.Cursor = Cursors.SizeAll;
            }
            else
            {
                this.Cursor = Cursors.Default;
            }
        }

        private void TitleBar_MouseUp(object? sender, MouseEventArgs e)
        {
            _isDragging = false;
        }

        private void ShowViewMenu()
        {
            var menu = new ContextMenuStrip();
            var theme = _themeManager.GetCurrentTheme();
            menu.BackColor = theme.WindowBackground;
            menu.ForeColor = theme.Text;
            menu.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            menu.AutoClose = true;
            
            // Button visibility items
            foreach (var kvp in _settings.ButtonVisibility.OrderBy(x => x.Key))
            {
                var visItem = new ToolStripMenuItem(kvp.Key.Replace("_", " "))
                {
                    Checked = kvp.Value,
                    CheckOnClick = true,
                    Tag = kvp.Key
                };
                visItem.Click += (s, e) =>
                {
                    if (s is ToolStripMenuItem item && item.Tag is string buttonId)
                    {
                        _settings.ButtonVisibility[buttonId] = item.Checked;
                        CreateButtons();
                        ApplyTheme();
                    }
                };
                menu.Items.Add(visItem);
            }
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Console toggle
            var consoleItem = new ToolStripMenuItem("Show Console")
            {
                Checked = _settings.ShowConsole,
                CheckOnClick = true
            };
            consoleItem.Click += (s, e) =>
            {
                _settings.ShowConsole = consoleItem.Checked;
                UpdateConsoleVisibility();
                ApplyTheme();
            };
            menu.Items.Add(consoleItem);
            
            menu.Show(this, _viewButtonRect.Left, _viewButtonRect.Bottom + 5);
        }
        
        private void ShowLinksMenu()
        {
            var menu = new ContextMenuStrip();
            var theme = _themeManager.GetCurrentTheme();
            menu.BackColor = theme.WindowBackground;
            menu.ForeColor = theme.Text;
            menu.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            menu.AutoClose = true;
            menu.ShowImageMargin = false;
            
            // Links
            var links = new Dictionary<string, string>
            {
                ["Mapping API Wiki"] = "https://github.com/KZGlobalTeam/cs2kz-metamod/wiki/Mapping-API",
                ["CS2KZ Metamod"] = "https://github.com/KZGlobalTeam/cs2kz-metamod",
                ["cs2kz.org"] = "https://cs2kz.org",
                ["Source2Viewer"] = "https://s2v.app/"
            };
            
            foreach (var link in links)
            {
                var linkItem = new ToolStripMenuItem(link.Key);
                linkItem.Click += (s, e) =>
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = link.Value,
                            UseShellExecute = true
                        });
                    }
                    catch { }
                };
                menu.Items.Add(linkItem);
            }
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Assets section
            var assetsLabel = new ToolStripLabel("Assets");
            menu.Items.Add(assetsLabel);
            
            var assetLinks = new Dictionary<string, string>
            {
                ["  AmbientCG"] = "https://ambientcg.com/",
                ["  Sketchfab"] = "https://sketchfab.com/search?features=downloadable&type=models",
                ["  Meshes"] = "https://www.thebasemesh.com/model-library",
                ["  JP-2499/AgX"] = "https://codeberg.org/GameChaos/s2-open-domain-lut-generator/releases/tag/jp2499-v1",
                ["  GameBanana"] = "https://gamebanana.com/games/4660"
            };
            
            foreach (var link in assetLinks)
            {
                var linkItem = new ToolStripMenuItem(link.Key);
                linkItem.Click += (s, e) =>
                {
                    try
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = link.Value,
                            UseShellExecute = true
                        });
                    }
                    catch { }
                };
                menu.Items.Add(linkItem);
            }
            
            menu.Show(this, _linksButtonRect.Left, _linksButtonRect.Bottom + 5);
        }

        private void ShowSettingsMenu()
        {
            var menu = new ContextMenuStrip();
            var theme = _themeManager.GetCurrentTheme();
            menu.BackColor = theme.WindowBackground;
            menu.ForeColor = theme.Text;
            menu.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            menu.AutoClose = true;
            menu.ShowCheckMargin = true;
            menu.ShowImageMargin = false;
            
            // Theme submenu
            var themeMenu = new ToolStripMenuItem("Theme");
            themeMenu.DropDown.BackColor = theme.WindowBackground;
            themeMenu.DropDown.ForeColor = theme.Text;
            themeMenu.DropDown.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            ((ToolStripDropDownMenu)themeMenu.DropDown).ShowCheckMargin = true;
            ((ToolStripDropDownMenu)themeMenu.DropDown).ShowImageMargin = false;
            themeMenu.DropDown.ShowItemToolTips = false;
            foreach (var themeName in _themeManager.Themes.Keys)
            {
                var themeItem = new ToolStripMenuItem(themeName)
                {
                    Checked = themeName == _settings.Theme
                };
                themeItem.Click += (s, e) =>
                {
                    _settings.Theme = themeName;
                    _themeManager.CurrentTheme = themeName;
                    ApplyTheme();
                };
                themeMenu.DropDownItems.Add(themeItem);
            }
            menu.Items.Add(themeMenu);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Button Columns submenu
            var columnsMenu = new ToolStripMenuItem("Button Columns");
            columnsMenu.DropDown.BackColor = theme.WindowBackground;
            columnsMenu.DropDown.ForeColor = theme.Text;
            columnsMenu.DropDown.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            ((ToolStripDropDownMenu)columnsMenu.DropDown).ShowCheckMargin = true;
            ((ToolStripDropDownMenu)columnsMenu.DropDown).ShowImageMargin = false;
            columnsMenu.DropDown.ShowItemToolTips = false;
            int maxCols = _settings.ButtonVisibility.Count(kvp => kvp.Value);
            for (int i = 1; i <= maxCols; i++)
            {
                int cols = i;
                var colItem = new ToolStripMenuItem($"{cols} Column" + (cols > 1 ? "s" : ""))
                {
                    Checked = _settings.GridColumns == cols
                };
                colItem.Click += (s, e) =>
                {
                    _settings.GridColumns = cols;
                    CreateButtons();
                    ApplyTheme();
                    ApplyStatusIndicators();
                };
                columnsMenu.DropDownItems.Add(colItem);
            }
            menu.Items.Add(columnsMenu);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Scale submenu
            var scaleMenu = new ToolStripMenuItem("Scale");
            scaleMenu.DropDown.BackColor = theme.WindowBackground;
            scaleMenu.DropDown.ForeColor = theme.Text;
            scaleMenu.DropDown.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            ((ToolStripDropDownMenu)scaleMenu.DropDown).ShowCheckMargin = true;
            ((ToolStripDropDownMenu)scaleMenu.DropDown).ShowImageMargin = false;
            scaleMenu.DropDown.ShowItemToolTips = false;
            
            float[] scaleValues = { 0.75f, 1.0f, 1.25f, 1.5f, 1.75f };
            string[] scaleLabels = { "75%", "100%", "125%", "150%", "175%" };
            
            for (int i = 0; i < scaleValues.Length; i++)
            {
                float scaleValue = scaleValues[i];
                string scaleLabel = scaleLabels[i];
                var scaleItem = new ToolStripMenuItem(scaleLabel)
                {
                    Checked = Math.Abs(_settings.Scale - scaleValue) < 0.01f
                };
                scaleItem.Click += (s, e) =>
                {
                    _settings.Scale = scaleValue;
                    CreateButtons();
                    ApplyTheme();
                    ApplyStatusIndicators();
                };
                scaleMenu.DropDownItems.Add(scaleItem);
            }
            menu.Items.Add(scaleMenu);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Opacity submenu
            var opacityMenu = new ToolStripMenuItem("Opacity");
            opacityMenu.DropDown.BackColor = theme.WindowBackground;
            opacityMenu.DropDown.ForeColor = theme.Text;
            opacityMenu.DropDown.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            ((ToolStripDropDownMenu)opacityMenu.DropDown).ShowCheckMargin = true;
            ((ToolStripDropDownMenu)opacityMenu.DropDown).ShowImageMargin = false;
            opacityMenu.DropDown.ShowItemToolTips = false;
            
            int[] opacityValues = { 10, 20, 30, 40, 50, 60, 70, 80, 90, 100 };
            
            foreach (int opacity in opacityValues)
            {
                float opacityValue = opacity / 100f;
                var opacityItem = new ToolStripMenuItem($"{opacity}%")
                {
                    Checked = Math.Abs(_settings.WindowOpacity - opacityValue) < 0.01f
                };
                opacityItem.Click += (s, e) =>
                {
                    _settings.WindowOpacity = opacityValue;
                    this.Opacity = opacityValue;
                };
                opacityMenu.DropDownItems.Add(opacityItem);
            }
            menu.Items.Add(opacityMenu);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Auto-Update Source2Viewer toggle
            var autoUpdateItem = new ToolStripMenuItem("Auto-Update Source2Viewer")
            {
                Checked = _settings.AutoUpdateSource2Viewer,
                CheckOnClick = true
            };
            autoUpdateItem.Click += (s, e) =>
            {
                _settings.AutoUpdateSource2Viewer = autoUpdateItem.Checked;
            };
            menu.Items.Add(autoUpdateItem);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Always On Top toggle
            var alwaysOnTopItem = new ToolStripMenuItem("Always On Top")
            {
                Checked = _settings.AlwaysOnTop,
                CheckOnClick = true
            };
            alwaysOnTopItem.Click += (s, e) =>
            {
                _settings.AlwaysOnTop = alwaysOnTopItem.Checked;
                this.TopMost = alwaysOnTopItem.Checked;
            };
            menu.Items.Add(alwaysOnTopItem);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Manually Verify Files option
            var verifyFilesItem = new ToolStripMenuItem("Manually Verify Files");
            verifyFilesItem.Click += (s, e) =>
            {
                VerifyGameInfoFiles();
            };
            menu.Items.Add(verifyFilesItem);
            
            menu.Items.Add(new ToolStripSeparator());
            
            // Open Temp Folder option
            var openTempItem = new ToolStripMenuItem("Open Temp Folder");
            openTempItem.Click += (s, e) =>
            {
                string tempPath = Path.Combine(Path.GetTempPath(), ".CS2KZ-mapping-tools");
                if (!Directory.Exists(tempPath))
                {
                    Directory.CreateDirectory(tempPath);
                }
                Process.Start(new ProcessStartInfo
                {
                    FileName = tempPath,
                    UseShellExecute = true,
                    Verb = "open"
                });
            };
            menu.Items.Add(openTempItem);
            
            menu.Show(this, _settingsButtonRect.Left, _settingsButtonRect.Bottom + 5);
        }
        
        private void ShowAboutMenu()
        {
            var menu = new ContextMenuStrip();
            var theme = _themeManager.GetCurrentTheme();
            menu.BackColor = theme.WindowBackground;
            menu.ForeColor = theme.Text;
            menu.Renderer = new ToolStripProfessionalRenderer(new CustomColorTable(theme));
            menu.AutoClose = true;
            menu.ShowImageMargin = false;
            
            // Made by jakke (links to Steam)
            var jakkeItem = new ToolStripMenuItem("Made by jakke");
            jakkeItem.Click += (s, e) =>
            {
                try
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "https://steamcommunity.com/profiles/76561197981712950",
                        UseShellExecute = true
                    });
                }
                catch { }
            };
            menu.Items.Add(jakkeItem);
            
            // Open Github
            var githubItem = new ToolStripMenuItem("Open Github");
            githubItem.Click += (s, e) =>
            {
                try
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = "https://github.com/jakkekz/CS2KZ-Mapping-Tools",
                        UseShellExecute = true
                    });
                }
                catch { }
            };
            menu.Items.Add(githubItem);
            
            // Show menu aligned to right side of About button
            menu.Show(this, _aboutButtonRect.Right - menu.Width, _aboutButtonRect.Bottom + 5);
        }
        
        private async void CheckForUpdates()
        {
            try
            {
                var client = new System.Net.Http.HttpClient();
                client.DefaultRequestHeaders.Add("User-Agent", "CS2KZ-Mapping-Tools");
                client.Timeout = TimeSpan.FromSeconds(10);
                
                string apiUrl = "https://api.github.com/repos/jakkekz/CS2KZ-Mapping-Tools/releases/latest";
                var response = await client.GetStringAsync(apiUrl);
                
                // Parse JSON response
                var jsonStart = response.IndexOf("\"tag_name\":");
                if (jsonStart == -1)
                {
                    MessageBox.Show("Unable to check for updates.", "Update Check", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return;
                }
                
                var versionStart = response.IndexOf("\"", jsonStart + 11) + 1;
                var versionEnd = response.IndexOf("\"", versionStart);
                var latestVersion = response.Substring(versionStart, versionEnd - versionStart);
                
                // Get download URL
                var urlStart = response.IndexOf("\"browser_download_url\":");
                if (urlStart != -1)
                {
                    var downloadUrlStart = response.IndexOf("\"", urlStart + 23) + 1;
                    var downloadUrlEnd = response.IndexOf("\"", downloadUrlStart);
                    var downloadUrl = response.Substring(downloadUrlStart, downloadUrlEnd - downloadUrlStart);
                    
                    // Mark update as available and refresh UI
                    _updateAvailable = true;
                    this.Invalidate(new Rectangle(0, 0, this.ClientSize.Width, TitleBarHeight));
                    
                    var result = MessageBox.Show(
                        $"Latest version: {latestVersion}\\n\\nWould you like to download the update?",
                        "Update Available",
                        MessageBoxButtons.YesNo,
                        MessageBoxIcon.Information);
                    
                    if (result == DialogResult.Yes)
                    {
                        Process.Start(new ProcessStartInfo
                        {
                            FileName = downloadUrl,
                            UseShellExecute = true
                        });
                    }
                }
                else
                {
                    // No update available
                    _updateAvailable = false;
                    this.Invalidate(new Rectangle(0, 0, this.ClientSize.Width, TitleBarHeight));
                    MessageBox.Show($"Latest version: {latestVersion}\\n\\nYou have the latest version!", "Up to Date", MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error checking for updates: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        
        private void Button_MouseDown(object? sender, MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left && sender is CustomButton button)
            {
                _draggingButton = button;
                _dragStartPoint = e.Location;
                _originalButtonLocation = button.Location;
                _isDraggingButton = false;
            }
        }
        
        private void Button_MouseMove(object? sender, MouseEventArgs e)
        {
            if (_draggingButton != null && e.Button == MouseButtons.Left)
            {
                // Check if mouse has moved enough to start dragging
                int dragThreshold = 5;
                if (Math.Abs(e.X - _dragStartPoint.X) > dragThreshold || 
                    Math.Abs(e.Y - _dragStartPoint.Y) > dragThreshold)
                {
                    if (!_isDraggingButton)
                    {
                        _isDraggingButton = true;
                        _dropSuccessful = false;
                        
                        // Create visual representation of the dragging button
                        int buttonWidth = ButtonWidth;
                        int buttonHeight = ButtonHeight;
                        _dragButtonImage = new Bitmap(buttonWidth, buttonHeight);
                        
                        using (var g = Graphics.FromImage(_dragButtonImage))
                        {
                            g.SmoothingMode = SmoothingMode.AntiAlias;
                            var theme = _themeManager.GetCurrentTheme();
                            
                            // Draw button background
                            using (var brush = new SolidBrush(theme.ButtonBackground))
                            {
                                g.FillRectangle(brush, 0, 0, buttonWidth, buttonHeight);
                            }
                            
                            // Draw border
                            using (var pen = new Pen(theme.Border, 2))
                            {
                                g.DrawRectangle(pen, 1, 1, buttonWidth - 2, buttonHeight - 2);
                            }
                            
                            // Draw button content (icon and text)
                            if (_draggingButton.Image != null)
                            {
                                int iconSize = 24;
                                int iconX = (buttonWidth - iconSize) / 2;
                                int iconY = 10;
                                g.DrawImage(_draggingButton.Image, iconX, iconY, iconSize, iconSize);
                            }
                            
                            // Draw text
                            using (var brush = new SolidBrush(theme.Text))
                            using (var font = new Font("Roboto", 11F))
                            {
                                var sf = new StringFormat 
                                { 
                                    Alignment = StringAlignment.Center, 
                                    LineAlignment = StringAlignment.Far 
                                };
                                var textRect = new RectangleF(0, 0, buttonWidth, buttonHeight - 10);
                                g.DrawString(_draggingButton.Text, font, brush, textRect, sf);
                            }
                        }
                        
                        // Hide the original button
                        _draggingButton.Visible = false;
                        
                        // Initialize drag location
                        _dragButtonLocation = _draggingButton.Location;
                        _prevDragButtonLocation = Point.Empty;
                        
                        // Start the drag-drop operation
                        _draggingButton.DoDragDrop(_draggingButton.Tag as string ?? "", DragDropEffects.Move);
                    }
                }
            }
        }
        
        private void Button_MouseUp(object? sender, MouseEventArgs e)
        {
            // Clean up drag visuals and restore button to original position
            if (_draggingButton != null)
            {
                _draggingButton.Visible = true;
                _draggingButton.Location = _originalButtonLocation;
            }
            _draggingButton = null;
            _isDraggingButton = false;
            _dragButtonImage?.Dispose();
            _dragButtonImage = null;
            _prevDragButtonLocation = Point.Empty;
            this.Invalidate();
        }
        
        private void Button_QueryContinueDrag(object? sender, QueryContinueDragEventArgs e)
        {
            // If drag is cancelled, clean up immediately
            if (e.Action == DragAction.Cancel)
            {
                if (_draggingButton != null)
                {
                    _draggingButton.Visible = true;
                    _draggingButton.Location = _originalButtonLocation;
                    _draggingButton = null;
                    _isDraggingButton = false;
                    _dragButtonImage?.Dispose();
                    _dragButtonImage = null;
                    _prevDragButtonLocation = Point.Empty;
                    this.Invalidate();
                }
            }
            // If drag completed (drop), check if it was successful
            else if (e.Action == DragAction.Drop)
            {
                // Use BeginInvoke to check after DragDrop event has a chance to run
                this.BeginInvoke(new Action(() =>
                {
                    if (_draggingButton != null && !_dropSuccessful)
                    {
                        // Drop was not successful, restore button
                        _draggingButton.Visible = true;
                        _draggingButton.Location = _originalButtonLocation;
                        _draggingButton = null;
                        _isDraggingButton = false;
                        _dragButtonImage?.Dispose();
                        _dragButtonImage = null;
                        _prevDragButtonLocation = Point.Empty;
                        this.Invalidate();
                    }
                }));
            }
        }
        
        private void Button_GiveFeedback(object? sender, GiveFeedbackEventArgs e)
        {
            // Use the same cursor as title bar dragging
            e.UseDefaultCursors = false;
            this.Cursor = Cursors.SizeAll;
        }
        
        private void MainForm_DragOver(object? sender, DragEventArgs e)
        {
            // Update drag button position to follow cursor
            if (_isDraggingButton && _dragButtonImage != null)
            {
                Point clientPoint = this.PointToClient(new Point(e.X, e.Y));
                int buttonWidth = _dragButtonImage.Width;
                int buttonHeight = _dragButtonImage.Height;
                Point newLocation = new Point(clientPoint.X - buttonWidth / 2, clientPoint.Y - buttonHeight / 2);
                
                // Only redraw if position actually changed
                if (newLocation != _dragButtonLocation)
                {
                    // Invalidate old position (including shadow)
                    if (_prevDragButtonLocation != Point.Empty)
                    {
                        this.Invalidate(new Rectangle(
                            _prevDragButtonLocation.X - 2,
                            _prevDragButtonLocation.Y - 2,
                            buttonWidth + 10,
                            buttonHeight + 10));
                    }
                    
                    _prevDragButtonLocation = _dragButtonLocation;
                    _dragButtonLocation = newLocation;
                    
                    // Invalidate new position (including shadow)
                    this.Invalidate(new Rectangle(
                        _dragButtonLocation.X - 2,
                        _dragButtonLocation.Y - 2,
                        buttonWidth + 10,
                        buttonHeight + 10));
                    
                    // Force immediate update for smooth movement
                    this.Update();
                }
            }
            
            // Always show move cursor during drag, even if drop location is invalid
            e.Effect = DragDropEffects.Move;
        }
        
        private void MainForm_DragDrop(object? sender, DragEventArgs e)
        {
            // Drop on form background (not on a button) - reject the drop
            // The button will be restored to original position by Button_QueryContinueDrag
            _dropSuccessful = false;
        }
        
        private void Button_DragOver(object? sender, DragEventArgs e)
        {
            // Update drag button position to follow cursor (same as MainForm_DragOver)
            if (_isDraggingButton && _dragButtonImage != null)
            {
                Point clientPoint = this.PointToClient(new Point(e.X, e.Y));
                int buttonWidth = _dragButtonImage.Width;
                int buttonHeight = _dragButtonImage.Height;
                Point newLocation = new Point(clientPoint.X - buttonWidth / 2, clientPoint.Y - buttonHeight / 2);
                
                // Only redraw if position actually changed
                if (newLocation != _dragButtonLocation)
                {
                    // Invalidate old position (including shadow)
                    if (_prevDragButtonLocation != Point.Empty)
                    {
                        this.Invalidate(new Rectangle(
                            _prevDragButtonLocation.X - 2,
                            _prevDragButtonLocation.Y - 2,
                            buttonWidth + 10,
                            buttonHeight + 10));
                    }
                    
                    _prevDragButtonLocation = _dragButtonLocation;
                    _dragButtonLocation = newLocation;
                    
                    // Invalidate new position (including shadow)
                    this.Invalidate(new Rectangle(
                        _dragButtonLocation.X - 2,
                        _dragButtonLocation.Y - 2,
                        buttonWidth + 10,
                        buttonHeight + 10));
                    
                    // Force immediate update for smooth movement
                    this.Update();
                }
            }
            
            // Always allow drag over buttons
            e.Effect = DragDropEffects.Move;
        }
        
        private void Button_DragDrop(object? sender, DragEventArgs e)
        {
            if (sender is CustomButton targetButton && e.Data != null)
            {
                string? sourceButtonId = e.Data.GetData(typeof(string)) as string;
                string? targetButtonId = targetButton.Tag as string;
                
                if (!string.IsNullOrEmpty(sourceButtonId) && !string.IsNullOrEmpty(targetButtonId) 
                    && sourceButtonId != targetButtonId)
                {
                    // Swap button order
                    int sourceIndex = _settings.ButtonOrder.IndexOf(sourceButtonId);
                    int targetIndex = _settings.ButtonOrder.IndexOf(targetButtonId);
                    
                    if (sourceIndex >= 0 && targetIndex >= 0)
                    {
                        _settings.ButtonOrder[sourceIndex] = targetButtonId;
                        _settings.ButtonOrder[targetIndex] = sourceButtonId;
                        _settings.SaveSettings();
                        
                        // Mark drop as successful
                        _dropSuccessful = true;
                        
                        // Clean up drag state before recreating buttons
                        _draggingButton = null;
                        _isDraggingButton = false;
                        _dragButtonImage?.Dispose();
                        _dragButtonImage = null;
                        
                        // Recreate buttons with new order
                        CreateButtons();
                        ApplyTheme();
                        ApplyStatusIndicators();
                    }
                }
                else
                {
                    // No swap occurred, restore visibility and position
                    if (_draggingButton != null)
                        _draggingButton.Visible = true;
                }
                
                // Final cleanup
                _draggingButton = null;
                _dragButtonImage?.Dispose();
                _dragButtonImage = null;
                _isDraggingButton = false;
                _prevDragButtonLocation = Point.Empty;
                this.Invalidate();
            }
        }

        private void MainForm_FormClosing(object? sender, FormClosingEventArgs e)
        {
            _processCheckTimer?.Stop();
            _processCheckTimer?.Dispose();
            _updateCheckTimer?.Stop();
            _updateCheckTimer?.Dispose();
            _settings.WindowPosition = this.Location;
            _settings.SaveSettings();
        }
        
        private void ProcessCheckTimer_Tick(object? sender, EventArgs e)
        {
            UpdateCS2DependentButtons();
        }
        
        private async void UpdateCheckTimer_Tick(object? sender, EventArgs e)
        {
            _updateCheckCount++;
            bool checkRemote = (_updateCheckCount % 30 == 0); // Check remote every 5 minutes (every 30th tick)
            
            await CheckMetamodUpdatesAsync(checkRemote: checkRemote);
            await CheckSource2ViewerVersionAsync(checkRemote: checkRemote);
        }
        
        private async Task CheckMetamodUpdatesAsync(bool checkRemote = true)
        {
            if (_metamodUpdater == null) return;
            
            try
            {
                var status = await _metamodUpdater.CheckForUpdatesAsync(checkRemote);
                
                if (!string.IsNullOrEmpty(status.Error))
                {
                    Debug.WriteLine($"Update check error: {status.Error}");
                    return;
                }
                
                // Determine if not installed at all
                bool notInstalled = !status.MetamodInstalled || !status.CS2KZInstalled;
                
                // Determine if updates are needed (only check if installed)
                bool hasUpdate = !notInstalled && (status.MetamodUpdateAvailable || 
                                status.CS2KZUpdateAvailable || 
                                status.MappingAPIUpdateAvailable);
                
                // Check if everything is installed and up to date
                bool isUpToDate = !notInstalled && status.MetamodInstalled && status.CS2KZInstalled && 
                                 !status.MetamodUpdateAvailable && 
                                 !status.CS2KZUpdateAvailable && 
                                 !status.MappingAPIUpdateAvailable;
                
                Debug.WriteLine($"Metamod Check - MetamodInstalled: {status.MetamodInstalled}, CS2KZInstalled: {status.CS2KZInstalled}");
                Debug.WriteLine($"Metamod Status - NotInstalled: {notInstalled}, HasUpdate: {hasUpdate}, IsUpToDate: {isUpToDate}");
                
                // Cache the status
                _metamodButtonsNotInstalled = notInstalled;
                _metamodButtonsHaveUpdate = hasUpdate;
                _metamodButtonsUpToDate = isUpToDate;
                
                // Update indicators for metamod-dependent buttons
                string[] metamodButtons = { "mapping", "listen", "dedicated_server", "insecure" };
                
                foreach (var buttonId in metamodButtons)
                {
                    if (_buttons.ContainsKey(buttonId))
                    {
                        if (this.InvokeRequired)
                        {
                            this.Invoke((Action)(() =>
                            {
                                if (notInstalled)
                                    _buttons[buttonId].SetNotInstalled(true);
                                else if (hasUpdate)
                                    _buttons[buttonId].SetUpdateAvailable(true);
                                else if (isUpToDate)
                                    _buttons[buttonId].SetUpToDate(true);
                                else
                                    _buttons[buttonId].ClearStatusIndicator();
                            }));
                        }
                        else
                        {
                            if (notInstalled)
                                _buttons[buttonId].SetNotInstalled(true);
                            else if (hasUpdate)
                                _buttons[buttonId].SetUpdateAvailable(true);
                            else if (isUpToDate)
                                _buttons[buttonId].SetUpToDate(true);
                            else
                                _buttons[buttonId].ClearStatusIndicator();
                        }
                    }
                }
                
                Debug.WriteLine($"Metamod update check: Metamod={status.MetamodUpdateAvailable}, CS2KZ={status.CS2KZUpdateAvailable}, MappingAPI={status.MappingAPIUpdateAvailable}, UpToDate={isUpToDate}");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Update check failed: {ex.Message}");
            }
        }
        
        private void UpdateCS2DependentButtons()
        {
            bool cs2Running = Process.GetProcessesByName("cs2").Length > 0;
            bool hammerRunning = Process.GetProcessesByName("hammer").Length > 0;
            
            string[] cs2DependentButtons = { "listen", "insecure" };
            
            foreach (var buttonId in cs2DependentButtons)
            {
                if (_buttons.ContainsKey(buttonId))
                {
                    _buttons[buttonId].Enabled = !cs2Running;
                }
            }
            
            // Mapping button disabled if CS2 or Hammer is running
            if (_buttons.ContainsKey("mapping"))
            {
                _buttons["mapping"].Enabled = !cs2Running && !hammerRunning;
            }
        }

        private void Button_Click(object? sender, EventArgs e)
        {
            if (sender is CustomButton button && button.Tag is string buttonId)
            {
                LaunchTool(buttonId);
            }
        }

        private void LaunchTool(string toolId)
        {
            try
            {
                string basePath = ResourceExtractor.ExtractResources();
                
                // Check if this is a metamod-dependent tool
                string[] metamodDependentTools = { "mapping", "listen", "dedicated_server", "insecure" };
                if (metamodDependentTools.Contains(toolId))
                {
                    LaunchMetamodDependentToolAsync(toolId);
                    return;
                }
                
                switch (toolId)
                {
                    case "cs2importer":
                        LaunchScript("porting/cs2importer.py");
                        break;
                    
                    case "skyboxconverter":
                        LaunchScript("skybox_gui.py");
                        break;
                    
                    case "vtf2png":
                        LaunchScript("vtf2png_gui.py");
                        break;
                    
                    case "loading_screen":
                        LaunchScript("loading_screen_gui.py");
                        break;
                    
                    case "point_worldtext":
                        LaunchPointWorldTextAsync();
                        break;
                    
                    case "sounds":
                        LaunchScript("sounds.py");
                        break;
                        
                    case "fix_cs2":
                        FixCS2GameInfoAsync();
                        break;
                        
                    case "source2viewer":
                        LaunchSource2ViewerAsync();
                        break;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error launching tool: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        
        private async void LaunchMetamodDependentToolAsync(string toolId)
        {
            try
            {
                if (toolId == "mapping")
                {
                    // Use C# MappingManager for the mapping tool
                    await LaunchMappingToolAsync();
                }
                else if (toolId == "listen")
                {
                    // Use C# ListenManager for the listen server
                    await LaunchListenServerAsync();
                }
                else if (toolId == "dedicated_server")
                {
                    // Use C# DedicatedManager for the dedicated server
                    await LaunchDedicatedServerAsync();
                }
                else if (toolId == "insecure")
                {
                    // Use C# InsecureManager for insecure mode
                    await LaunchInsecureAsync();
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        
        private void LaunchScript(string scriptPath)
        {
            string basePath = ResourceExtractor.ExtractResources();
            string fullScriptPath = Path.Combine(basePath, "scripts", scriptPath);
            
            // Check if Python script exists
            if (File.Exists(fullScriptPath))
            {
                // For mapping-related scripts, add flags to skip metamod/cs2kz downloads
                // since the C# side handles that
                string extraArgs = "";
                if (scriptPath == "mapping.py" || scriptPath == "listen.py" || 
                    scriptPath == "run-dedicated.py" || scriptPath == "run-insecure.py")
                {
                    extraArgs = " --no-update-metamod --no-update-cs2kz";
                }
                
                // Launch Python script in a cmd window that stays open on error
                Process.Start(new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = $"/k python \"{fullScriptPath}\"{extraArgs}",
                    UseShellExecute = true,
                    WorkingDirectory = Path.GetDirectoryName(fullScriptPath)
                });
            }
            else
            {
                // Check if .exe version exists
                string exePath = fullScriptPath.Replace(".py", ".exe");
                if (File.Exists(exePath))
                {
                    Process.Start(new ProcessStartInfo
                    {
                        FileName = exePath,
                        UseShellExecute = true,
                        WorkingDirectory = Path.GetDirectoryName(exePath)
                    });
                }
                else
                {
                    MessageBox.Show($"Script not found: {fullScriptPath}\nAlso checked: {exePath}", 
                        "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
        }
        
        private async void LaunchSource2ViewerAsync()
        {
            try
            {
                Debug.WriteLine("LaunchSource2ViewerAsync called");
                var updater = new Source2ViewerUpdater();
                
                // Check if auto-update is disabled
                if (!_settings.AutoUpdateSource2Viewer)
                {
                    // Just launch Source2Viewer directly without updating
                    bool launchSuccess = updater.LaunchApp();
                    if (!launchSuccess)
                    {
                        MessageBox.Show("Source2Viewer not found. Please enable auto-update in settings to download it.",
                            "Source2Viewer Not Found", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    }
                    return;
                }
                
                // Auto-update is enabled, proceed with update check
                // Collect status messages for debugging
                var statusMessages = new System.Text.StringBuilder();
                
                // Hook up progress events
                updater.DownloadProgressChanged += (s, progress) =>
                {
                    if (_buttons.ContainsKey("source2viewer"))
                    {
                        this.Invoke((Action)(() =>
                        {
                            _buttons["source2viewer"].SetDownloadProgress(progress);
                        }));
                    }
                };
                
                updater.StatusChanged += (s, status) =>
                {
                    Debug.WriteLine($"S2V: {status}");
                    statusMessages.AppendLine(status);
                };
                
                // Clear progress indicator when done
                bool success = await updater.UpdateAndLaunchAsync();
                
                if (_buttons.ContainsKey("source2viewer"))
                {
                    _buttons["source2viewer"].ClearDownloadProgress();
                }
                
                // Check version status after update/launch
                await CheckSource2ViewerVersionAsync();
                
                if (!success)
                {
                    MessageBox.Show($"Failed to update or launch Source2Viewer.\n\nDetails:\n{statusMessages}", 
                        "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
            }
            catch (Exception ex)
            {
                if (_buttons.ContainsKey("source2viewer"))
                {
                    _buttons["source2viewer"].ClearDownloadProgress();
                }
                
                MessageBox.Show($"Error with Source2Viewer: {ex.Message}\n\nStack trace:\n{ex.StackTrace}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
        
        private async Task CheckSource2ViewerVersionAsync(bool checkRemote = true)
        {
            try
            {
                var updater = new Source2ViewerUpdater();
                string? remoteVersion = checkRemote ? await updater.GetRemoteVersionAsync() : null;
                string localVersion = updater.GetLocalVersion();
                
                // Determine status
                // Show red dot if: not installed at all
                bool notInstalled = localVersion == "0";
                // Show yellow dot if: installed but remote check succeeded AND version mismatch
                bool hasUpdate = !notInstalled && !string.IsNullOrEmpty(remoteVersion) && localVersion != remoteVersion;
                // Show green dot if: installed AND (versions match OR remote check failed)
                bool isUpToDate = !notInstalled && (string.IsNullOrEmpty(remoteVersion) || localVersion == remoteVersion);
                
                // Cache the status
                _s2vNotInstalled = notInstalled;
                _s2vHasUpdate = hasUpdate;
                _s2vUpToDate = isUpToDate;
                
                if (_buttons.ContainsKey("source2viewer"))
                {
                    if (this.InvokeRequired)
                    {
                        this.Invoke((Action)(() =>
                        {
                            if (notInstalled)
                            {
                                Debug.WriteLine("Setting S2V not-installed indicator (red)");
                                _buttons["source2viewer"].SetNotInstalled(true);
                            }
                            else if (hasUpdate)
                            {
                                Debug.WriteLine("Setting S2V update indicator (yellow)");
                                _buttons["source2viewer"].SetUpdateAvailable(true);
                            }
                            else if (isUpToDate)
                            {
                                Debug.WriteLine("Setting S2V up-to-date indicator (green)");
                                _buttons["source2viewer"].SetUpToDate(true);
                            }
                            else
                            {
                                Debug.WriteLine("Clearing S2V indicator");
                                _buttons["source2viewer"].ClearStatusIndicator();
                            }
                        }));
                    }
                    else
                    {
                        if (notInstalled)
                        {
                            Debug.WriteLine("Setting S2V not-installed indicator (red) - no invoke");
                            _buttons["source2viewer"].SetNotInstalled(true);
                        }
                        else if (hasUpdate)
                        {
                            Debug.WriteLine("Setting S2V update indicator (yellow) - no invoke");
                            _buttons["source2viewer"].SetUpdateAvailable(true);
                        }
                        else if (isUpToDate)
                        {
                            Debug.WriteLine("Setting S2V up-to-date indicator (green) - no invoke");
                            _buttons["source2viewer"].SetUpToDate(true);
                        }
                        else
                        {
                            Debug.WriteLine("Clearing S2V indicator - no invoke");
                            _buttons["source2viewer"].ClearStatusIndicator();
                        }
                    }
                }
                else
                {
                    Debug.WriteLine("S2V button NOT found in _buttons dictionary!");
                }
            }
            catch (Exception)
            {
            }
        }

        private async Task LaunchMappingToolAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                // Log to main console
                OnLogMessage("Launching CS2KZ Mapping Tool...");
                
                // Execute mapping workflow
                await _mappingManager.ExecuteMappingWorkflowAsync(
                    _settings.AutoUpdateMetamod, 
                    _settings.AutoUpdateCS2KZ);
                    
                OnLogMessage("Mapping tool launched successfully!");
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error launching mapping tool: {ex.Message}");
                MessageBox.Show($"Error launching mapping tool: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task LaunchListenServerAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                // Log to main console
                OnLogMessage("Launching CS2KZ Listen Server...");
                
                // Execute listen server workflow
                await _listenManager.RunListenServerProcessAsync(
                    _settings.AutoUpdateMetamod, 
                    _settings.AutoUpdateCS2KZ);
                    
                OnLogMessage("Listen server process completed!");
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error launching listen server: {ex.Message}");
                
                // Try to restore gameinfo files if there was an error
                OnLogMessage("Attempting to restore gameinfo files due to error...");
                try
                {
                    await _listenManager.ForceRestoreGameInfoAsync();
                    OnLogMessage("✓ GameInfo files restored");
                }
                catch (Exception restoreEx)
                {
                    OnLogMessage($"Failed to restore gameinfo files: {restoreEx.Message}");
                }
                
                MessageBox.Show($"Error launching listen server: {ex.Message}\n\nGameInfo restoration attempted. Try restarting CS2.", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task LaunchDedicatedServerAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                // Log to main console
                OnLogMessage("Launching CS2 Dedicated Server...");
                
                // Execute dedicated server workflow
                await _dedicatedManager.RunDedicatedServerProcessAsync();
                    
                OnLogMessage("Dedicated server process completed!");
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error launching dedicated server: {ex.Message}");
                
                MessageBox.Show($"Error launching dedicated server: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async Task LaunchInsecureAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                // Log to main console
                OnLogMessage("Launching CS2 in Insecure Mode...");
                
                // Execute insecure mode
                await _insecureManager.RunInsecureModeAsync();
                    
                OnLogMessage("Insecure mode session completed!");
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error launching insecure mode: {ex.Message}");
                
                MessageBox.Show($"Error launching insecure mode: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async void LaunchPointWorldTextAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                OnLogMessage("Opening Point World Text Generator...");
                
                // Show a simple input dialog for text
                var inputDialog = new PointWorldTextDialog(_themeManager);
                inputDialog.TextGenerated += async (text, outputPath, canvasWidth, canvasHeight, generateVmat, selectedAddon, filename) =>
                {
                    try
                    {
                        OnLogMessage($"Generating text image: '{text}'");
                        var result = await _pointWorldTextManager.GenerateTextWithOptionsAsync(
                            text, outputPath, canvasWidth, canvasHeight, generateVmat, selectedAddon, filename);
                        
                        if (result != null)
                        {
                            OnLogMessage($"✓ Text generation completed: {result}");
                        }
                        else
                        {
                            OnLogMessage("✗ Failed to generate text image");
                        }
                    }
                    catch (Exception genEx)
                    {
                        OnLogMessage($"Error generating text: {genEx.Message}");
                    }
                };
                
                inputDialog.Show();
                OnLogMessage("Point World Text Generator opened successfully!");
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error opening Point World Text Generator: {ex.Message}");
                
                MessageBox.Show($"Error opening Point World Text Generator: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private async void FixCS2GameInfoAsync()
        {
            try
            {
                // Show console if not visible
                if (!_settings.ShowConsole)
                {
                    _settings.ShowConsole = true;
                    UpdateConsoleVisibility();
                }
                
                OnLogMessage("Fixing CS2 GameInfo files...");
                await _listenManager.ForceRestoreGameInfoAsync();
                OnLogMessage("✓ CS2 GameInfo files have been restored to original state");
                
                MessageBox.Show("CS2 GameInfo files have been restored successfully!\n\nYou should now be able to start CS2 normally.", 
                    "CS2 Fixed", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch (Exception ex)
            {
                OnLogMessage($"Error fixing CS2: {ex.Message}");
                MessageBox.Show($"Error fixing CS2: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void VerifyGameInfoFiles()
        {
            try
            {
                string basePath = ResourceExtractor.ExtractResources();
                
                // Create a comprehensive Python script that matches the Python version's verify_game_files
                string tempScript = Path.Combine(Path.GetTempPath(), "verify_game_files_temp.py");
                string scriptContent = @"
import sys
import os
import winreg
import urllib.request

def get_cs2_path():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            steam_path, _ = winreg.QueryValueEx(key, 'SteamPath')
    except FileNotFoundError:
        print('✗ Steam installation not found')
        return None
    
    try:
        import vdf
    except ImportError:
        print('Installing vdf package...')
        import subprocess
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'vdf', '--quiet'])
        import vdf
    
    libraryfolders_path = os.path.join(steam_path, 'steamapps', 'libraryfolders.vdf')
    if not os.path.exists(libraryfolders_path):
        print('✗ Steam library folders not found')
        return None
    
    with open(libraryfolders_path, 'r', encoding='utf-8') as file:
        library_data = vdf.load(file)
    
    cs2_library_path = None
    if 'libraryfolders' in library_data:
        for _, folder in library_data['libraryfolders'].items():
            if 'apps' in folder and '730' in folder['apps']:
                cs2_library_path = folder['path']
                break
    
    if not cs2_library_path:
        print('✗ CS2 installation not found')
        return None
    
    cs2_path = os.path.join(cs2_library_path, 'steamapps', 'common', 'Counter-Strike Global Offensive')
    
    if not os.path.exists(cs2_path):
        print(f'✗ CS2 path not found: {cs2_path}')
        return None
    
    return cs2_path

def verify_game_files():
    print('Starting game file verification...')
    
    try:
        cs2_path = get_cs2_path()
        if not cs2_path:
            return
        
        print(f'Found CS2 at: {cs2_path}')
        
        # Files to restore from GitHub
        BASE_URL = 'https://raw.githubusercontent.com/SteamDatabase/GameTracking-CS2/refs/heads/master/'
        
        files_to_restore = [
            'game/csgo/gameinfo.gi',
            'game/csgo_core/gameinfo.gi',
            'game/bin/sdkenginetools.txt',
            'game/bin/assettypes_common.txt'
        ]
        
        files_restored = 0
        files_failed = 0
        
        for file_path in files_to_restore:
            url = BASE_URL + file_path
            full_path = os.path.join(cs2_path, file_path)
            
            try:
                print(f'Downloading {file_path}...')
                response = urllib.request.urlopen(url, timeout=10)
                
                if response.getcode() != 200:
                    print(f'✗ Failed to download {file_path} (HTTP {response.getcode()})')
                    files_failed += 1
                    continue
                
                content = response.read().decode('utf-8').replace('\n', '\r\n')
                
                # Create directory if needed
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write file
                with open(full_path, 'wb') as f:
                    f.write(content.encode('utf-8'))
                
                print(f'✓ Restored {file_path}')
                files_restored += 1
                
            except Exception as e:
                print(f'✗ Error restoring {file_path}: {e}')
                files_failed += 1
        
        # Summary
        print(f'\nVerification complete:')
        print(f'  ✓ {files_restored} files restored')
        if files_failed > 0:
            print(f'  ✗ {files_failed} files failed')
        
        # Check for and restore vpk.signatures.old
        vpk_signatures_old = os.path.join(cs2_path, 'game', 'csgo', 'vpk.signatures.old')
        vpk_signatures = os.path.join(cs2_path, 'game', 'csgo', 'vpk.signatures')
        
        if os.path.exists(vpk_signatures_old):
            try:
                # Remove existing vpk.signatures if it exists
                if os.path.exists(vpk_signatures):
                    os.remove(vpk_signatures)
                
                # Rename vpk.signatures.old back to vpk.signatures
                os.rename(vpk_signatures_old, vpk_signatures)
                print(f'  ✓ Restored vpk.signatures from backup')
                
            except Exception as e:
                print(f'  ✗ Failed to restore vpk.signatures: {e}')
        
        print('\nGame files have been restored to their original state.')
        print('(Addons folder preserved)')
        
    except Exception as e:
        print(f'✗ Error during verification: {e}')

if __name__ == '__main__':
    verify_game_files()
    input('\nPress Enter to close...')
";
                
                File.WriteAllText(tempScript, scriptContent);
                
                // Launch the verification script with a console window
                var startInfo = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = $"\"{tempScript}\"",
                    UseShellExecute = false,
                    CreateNoWindow = false,
                    WorkingDirectory = Path.Combine(basePath, "scripts")
                };
                
                Process.Start(startInfo);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error verifying files: {ex.Message}", 
                    "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void SetAlwaysOnTop(bool alwaysOnTop)
        {
            SetWindowPos(this.Handle,
                alwaysOnTop ? HWND_TOPMOST : HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE);
        }
    }
}
