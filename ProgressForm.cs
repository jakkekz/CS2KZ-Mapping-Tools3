using System;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    public partial class ProgressForm : Form
    {
        private RichTextBox _logTextBox = null!;
        private Button _closeButton = null!;
        private ProgressBar _progressBar = null!;
        private Label _statusLabel = null!;
        private readonly ThemeManager _themeManager;

        public ProgressForm(string title, ThemeManager themeManager)
        {
            _themeManager = themeManager;
            InitializeComponent(title);
            ApplyTheme();
        }

        private void InitializeComponent(string title)
        {
            this.Text = title;
            this.Size = new Size(700, 500);
            this.StartPosition = FormStartPosition.CenterParent;
            this.FormBorderStyle = FormBorderStyle.FixedDialog;
            this.MaximizeBox = false;
            this.MinimizeBox = false;

            // Log text box at the top, fills most of the space
            _logTextBox = new RichTextBox
            {
                Dock = DockStyle.Fill,
                ReadOnly = true,
                Font = new Font("Consolas", 9F),
                ScrollBars = RichTextBoxScrollBars.Vertical,
                WordWrap = false,
                Margin = new Padding(10, 10, 10, 5)
            };
            this.Controls.Add(_logTextBox);

            // Close button at the bottom
            _closeButton = new Button
            {
                Text = "Close",
                Size = new Size(100, 35),
                Dock = DockStyle.Bottom,
                Enabled = false,
                Margin = new Padding(10, 5, 10, 10)
            };
            _closeButton.Click += (s, e) => this.Close();
            this.Controls.Add(_closeButton);

            // Progress bar above close button
            _progressBar = new ProgressBar
            {
                Dock = DockStyle.Bottom,
                Height = 25,
                Style = ProgressBarStyle.Marquee,
                MarqueeAnimationSpeed = 30,
                Margin = new Padding(10, 5, 10, 5)
            };
            this.Controls.Add(_progressBar);

            // Status label above progress bar
            _statusLabel = new Label
            {
                Text = "Initializing...",
                Dock = DockStyle.Bottom,
                Height = 30,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(10, 5, 10, 5),
                Font = new Font("Segoe UI", 9F, FontStyle.Bold)
            };
            this.Controls.Add(_statusLabel);
        }

        private void ApplyTheme()
        {
            var theme = _themeManager.GetCurrentTheme();
            
            this.BackColor = theme.WindowBackground;
            this.ForeColor = theme.Text;
            
            _statusLabel.BackColor = theme.WindowBackground;
            _statusLabel.ForeColor = theme.Text;
            
            _logTextBox.BackColor = theme.WindowBackground;
            _logTextBox.ForeColor = theme.Text;
            
            _closeButton.BackColor = theme.ButtonBackground;
            _closeButton.ForeColor = theme.Text;
            _closeButton.FlatStyle = FlatStyle.Flat;
            _closeButton.FlatAppearance.BorderColor = theme.Border;
        }

        public void UpdateStatus(string status)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action<string>(UpdateStatus), status);
                return;
            }

            _statusLabel.Text = status;
        }

        public void AddLogMessage(string message)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action<string>(AddLogMessage), message);
                return;
            }

            _logTextBox.AppendText($"[{DateTime.Now:HH:mm:ss}] {message}{Environment.NewLine}");
            _logTextBox.ScrollToCaret();
        }

        public void SetProgress(int value, int maximum = 100)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action<int, int>(SetProgress), value, maximum);
                return;
            }

            if (_progressBar.Style != ProgressBarStyle.Blocks)
            {
                _progressBar.Style = ProgressBarStyle.Blocks;
                _progressBar.MarqueeAnimationSpeed = 0;
            }
            
            _progressBar.Maximum = maximum;
            _progressBar.Value = Math.Min(value, maximum);
        }

        public void SetIndeterminate()
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action(SetIndeterminate));
                return;
            }

            _progressBar.Style = ProgressBarStyle.Marquee;
            _progressBar.MarqueeAnimationSpeed = 30;
        }

        public void SetCompleted(bool success = true)
        {
            if (this.InvokeRequired)
            {
                this.Invoke(new Action<bool>(SetCompleted), success);
                return;
            }

            _progressBar.Style = ProgressBarStyle.Blocks;
            _progressBar.MarqueeAnimationSpeed = 0;
            _progressBar.Value = _progressBar.Maximum;
            
            _statusLabel.Text = success ? "Completed successfully!" : "Completed with errors.";
            _statusLabel.ForeColor = success ? Color.LimeGreen : Color.Orange;
            
            _closeButton.Enabled = true;
            _closeButton.Focus();
        }

        public async Task<bool> ExecuteTaskAsync<T>(Func<Task<T>> task, string initialStatus = "Working...")
        {
            UpdateStatus(initialStatus);
            SetIndeterminate();

            try
            {
                await task();
                SetCompleted(true);
                return true;
            }
            catch (Exception ex)
            {
                AddLogMessage($"Error: {ex.Message}");
                SetCompleted(false);
                return false;
            }
        }

        public async Task<bool> ExecuteTaskAsync(Func<Task> task, string initialStatus = "Working...")
        {
            UpdateStatus(initialStatus);
            SetIndeterminate();

            try
            {
                await task();
                SetCompleted(true);
                return true;
            }
            catch (Exception ex)
            {
                AddLogMessage($"Error: {ex.Message}");
                SetCompleted(false);
                return false;
            }
        }
    }
}