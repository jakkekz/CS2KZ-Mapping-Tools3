using System;
using System.Windows.Forms;

namespace CS2KZMappingTools
{
    internal static class Program
    {
        /// <summary>
        ///  The main entry point for the application.
        /// </summary>
        [STAThread]
        static void Main()
        {
            // Extract embedded resources on first run
            try
            {
                ResourceExtractor.ExtractResources();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to extract resources: {ex.Message}", 
                    "Initialization Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return;
            }

            Application.SetHighDpiMode(HighDpiMode.SystemAware);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}
