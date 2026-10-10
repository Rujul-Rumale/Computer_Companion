using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

class CompanionLauncher
{
    static void Main()
    {
        string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string pythonw = Path.Combine(dir, ".venv", "Scripts", "pythonw.exe");
        string mainPy = Path.Combine(dir, "main.py");

        if (!File.Exists(pythonw))
        {
            string sysDir = Environment.GetFolderPath(Environment.SpecialFolder.System);
            pythonw = Path.Combine(sysDir, "pythonw.exe");
            if (!File.Exists(pythonw))
            {
                Console.Error.WriteLine("pythonw.exe not found");
                Environment.Exit(1);
            }
        }

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = pythonw;
        psi.Arguments = "\"" + mainPy + "\"";
        psi.WorkingDirectory = dir;
        psi.UseShellExecute = false;
        psi.WindowStyle = ProcessWindowStyle.Hidden;
        psi.CreateNoWindow = true;

        try
        {
            Process proc = Process.Start(psi);
            if (proc != null) proc.WaitForExit();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("Launch failed: " + ex.Message);
            Environment.Exit(2);
        }
    }
}
