using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.IO;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    public class CustomButton : Button
    {
        private Theme? _theme;
        private float _scale = 1.0f;
        private int _downloadProgress = -1; // -1 means not downloading
        private bool _hasUpdate = false; // Indicates if an update is available
        private bool _isUpToDate = false; // Indicates if version is up to date
        private bool _isNotInstalled = false; // Indicates if software is not installed at all

        private string _iconPath = string.Empty;
        public string IconPath 
        { 
            get => _iconPath;
            set 
            {
                _iconPath = value;
                LoadIcon();
            }
        }
        
        public string? ToolTipText { get; set; }
        
        public void SetDownloadProgress(int progress)
        {
            _downloadProgress = progress;
            this.Invalidate();
        }
        
        public void ClearDownloadProgress()
        {
            _downloadProgress = -1;
            this.Invalidate();
        }
        
        public void SetUpdateAvailable(bool hasUpdate)
        {
            _hasUpdate = hasUpdate;
            _isUpToDate = false;
            _isNotInstalled = false;
            this.Invalidate();
        }
        
        public void SetUpToDate(bool isUpToDate)
        {
            _isUpToDate = isUpToDate;
            if (isUpToDate)
            {
                _hasUpdate = false;
                _isNotInstalled = false;
            }
            this.Invalidate();
        }
        
        public void SetNotInstalled(bool notInstalled)
        {
            _isNotInstalled = notInstalled;
            if (notInstalled)
            {
                _hasUpdate = false;
                _isUpToDate = false;
            }
            this.Invalidate();
        }
        
        public void ClearStatusIndicator()
        {
            _hasUpdate = false;
            _isUpToDate = false;
            _isNotInstalled = false;
            this.Invalidate();
        }
        
        public void SetScale(float scale)
        {
            _scale = scale;
            LoadIcon();
            // Reapply compact mode with new scale
            SetCompactMode(true);
            // Scale border size, but keep it at least 1
            this.FlatAppearance.BorderSize = Math.Max(1, (int)Math.Round(2 * _scale));
        }
        
        public void SetCompactMode(bool isCompact)
        {
            if (isCompact)
            {
                // Compact: Image above text, centered with padding
                this.TextAlign = ContentAlignment.BottomCenter;
                this.ImageAlign = ContentAlignment.TopCenter;
                this.TextImageRelation = TextImageRelation.ImageAboveText;
                this.Padding = new Padding(
                    (int)(4 * _scale), 
                    (int)(4 * _scale), 
                    (int)(4 * _scale), 
                    (int)(2 * _scale)
                );
                this.Font = new Font("Roboto", 11F * _scale, FontStyle.Regular);
            }
            else
            {
                // Non-compact: Larger font and icon, image at top with more padding
                this.TextAlign = ContentAlignment.BottomCenter;
                this.ImageAlign = ContentAlignment.TopCenter;
                this.TextImageRelation = TextImageRelation.ImageAboveText;
                this.Padding = new Padding(
                    (int)(6 * _scale), 
                    (int)(8 * _scale), 
                    (int)(6 * _scale), 
                    (int)(2 * _scale)
                );
                this.Font = new Font("Roboto", 13F * _scale, FontStyle.Regular);
            }
        }

        public CustomButton(Form parentForm)
        {
            this.FlatStyle = FlatStyle.Flat;
            this.FlatAppearance.BorderSize = 2;
            this.TextAlign = ContentAlignment.BottomCenter;
            this.ImageAlign = ContentAlignment.TopCenter;
            this.TextImageRelation = TextImageRelation.ImageAboveText;
            this.Padding = new Padding(5, 5, 5, 5);
            this.Font = new Font("Roboto", 7F, FontStyle.Regular);
            this.Cursor = Cursors.Hand;
            this.AutoSize = false;
        }

        public void ApplyTheme(Theme theme)
        {
            _theme = theme;
            this.ForeColor = theme.Text;
            this.BackColor = theme.ButtonBackground;
            this.FlatAppearance.BorderColor = theme.Border;
            this.FlatAppearance.MouseOverBackColor = theme.ButtonHover;
            this.FlatAppearance.MouseDownBackColor = theme.ButtonActive;
            this.Invalidate();
        }

        private void LoadIcon()
        {
            try
            {
                this.Image?.Dispose();
                
                if (string.IsNullOrEmpty(_iconPath) || !File.Exists(_iconPath))
                {
                    this.Image = null;
                    return;
                }

                int iconSize = (int)(50 * _scale);

                // Load .ico files and convert to bitmap
                if (_iconPath.EndsWith(".ico", StringComparison.OrdinalIgnoreCase))
                {
                    // Load the largest size from the icon file
                    using (var icon = new Icon(_iconPath, 256, 256))
                    using (var originalBitmap = icon.ToBitmap())
                    {
                        // Scale with high quality
                        var scaledBitmap = new Bitmap(iconSize, iconSize);
                        using (var g = Graphics.FromImage(scaledBitmap))
                        {
                            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
                            g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
                            g.DrawImage(originalBitmap, 0, 0, iconSize, iconSize);
                        }
                        this.Image = scaledBitmap;
                    }
                }
                else
                {
                    // Load and scale other image files
                    using (var originalBitmap = (Bitmap)Bitmap.FromFile(_iconPath))
                    {
                        var scaledBitmap = new Bitmap(iconSize, iconSize);
                        using (var g = Graphics.FromImage(scaledBitmap))
                        {
                            g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
                            g.SmoothingMode = System.Drawing.Drawing2D.SmoothingMode.HighQuality;
                            g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
                            g.DrawImage(originalBitmap, 0, 0, iconSize, iconSize);
                        }
                        this.Image = scaledBitmap;
                    }
                }
            }
            catch
            {
                this.Image = null;
            }
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
        }
        
        protected override void OnPaint(PaintEventArgs pevent)
        {
            base.OnPaint(pevent);
            
            var g = pevent.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            
            // Draw status indicator dot in top-right corner (only if not downloading)
            if (_downloadProgress < 0)
            {
                Color? dotColor = null;
                
                if (_isNotInstalled)
                {
                    // Red for not installed
                    dotColor = Color.FromArgb(200, 220, 50, 50);
                }
                else if (_hasUpdate)
                {
                    // Yellow-orange for updates available
                    dotColor = Color.FromArgb(200, 255, 180, 0);
                }
                else if (_isUpToDate)
                {
                    // Green for up to date
                    dotColor = Color.FromArgb(200, 0, 200, 80);
                }
                
                if (dotColor.HasValue)
                {
                    int dotSize = (int)(8 * _scale);
                    int dotX = this.Width - dotSize - (int)(4 * _scale);
                    int dotY = (int)(4 * _scale);
                    
                    using (var dotBrush = new SolidBrush(dotColor.Value))
                    {
                        g.FillEllipse(dotBrush, dotX, dotY, dotSize, dotSize);
                    }
                }
            }
            
            // Draw download progress indicator on right side
            if (_downloadProgress >= 0 && _downloadProgress <= 100)
            {
                int barWidth = (int)(10 * _scale);  // Wider bar for better visibility
                int barHeight = this.Height - (int)(8 * _scale);
                int barX = this.Width - barWidth - (int)(4 * _scale);
                int barY = (int)(4 * _scale);
                
                // Darker background with border for better visibility
                using (var bgBrush = new SolidBrush(Color.FromArgb(120, 0, 0, 0)))
                {
                    g.FillRectangle(bgBrush, barX, barY, barWidth, barHeight);
                }
                
                // Border around the bar
                using (var borderPen = new Pen(Color.FromArgb(150, Color.White), 1))
                {
                    g.DrawRectangle(borderPen, barX, barY, barWidth - 1, barHeight - 1);
                }
                
                // Progress (bottom to top) with bright contrasting color
                int progressHeight = (int)((barHeight * _downloadProgress) / 100f);
                int progressY = barY + barHeight - progressHeight;
                
                // Bright green that stands out against dark backgrounds
                using (var progressBrush = new SolidBrush(Color.FromArgb(255, 0, 255, 100)))
                {
                    g.FillRectangle(progressBrush, barX + 1, progressY, barWidth - 2, progressHeight);
                }
            }
        }

        private GraphicsPath GetRoundedRectangle(Rectangle rect, int radius)
        {
            var path = new GraphicsPath();
            int diameter = radius * 2;
            
            // Adjust rectangle to account for pen width
            rect = new Rectangle(rect.X + 1, rect.Y + 1, rect.Width - 2, rect.Height - 2);
            
            path.AddArc(rect.X, rect.Y, diameter, diameter, 180, 90);
            path.AddArc(rect.Right - diameter, rect.Y, diameter, diameter, 270, 90);
            path.AddArc(rect.Right - diameter, rect.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(rect.X, rect.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            
            return path;
        }

        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
        }
    }
}
