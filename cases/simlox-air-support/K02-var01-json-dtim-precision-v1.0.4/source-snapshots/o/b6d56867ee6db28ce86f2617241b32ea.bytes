using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
namespace Issue18SelectedQueryV1 {
 public sealed class Observation {
  public uint RequestedPid,ReturnedPid,Access,ReturnedLength;
  public string Handle,CreationFiletime,Image,ExpectedImage;
  public bool OpenReturned,TimesReturned,ImageReturned,CloseAttempted,ClosedActual;
  public int OpenError,PidError,TimesError,ImageError,CloseError;
 }
 public static class Query {
  [StructLayout(LayoutKind.Sequential)] struct FT {public uint Low,High; public ulong Value {get{return ((ulong)High<<32)|Low;}}}
  [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,uint pid);
  [DllImport("kernel32.dll",SetLastError=true)] static extern uint GetProcessId(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out FT creation,out FT exit,out FT kernel,out FT user);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool QueryFullProcessImageNameW(IntPtr h,uint flags,StringBuilder image,ref uint length);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr h);
  static readonly Dictionary<IntPtr,Observation> owned=new Dictionary<IntPtr,Observation>();
  public static readonly List<Observation> Records=new List<Observation>();
  static void Need(bool ok,string why){if(!ok)throw new InvalidOperationException(why);}
  public static IntPtr Acquire(uint pid,uint access) {
   Need(access==0x1000||(pid==44184&&access==0x101001),"query-only or exact reviewed benign recovery access");
   var r=new Observation{RequestedPid=pid,Access=access};Records.Add(r);
   IntPtr h=OpenProcess(access,false,pid);int e=Marshal.GetLastWin32Error();
   r.OpenReturned=true;r.OpenError=e;r.Handle=h.ToInt64().ToString(CultureInfo.InvariantCulture);
   Need(h!=IntPtr.Zero&&h!=new IntPtr(-1),"OpenProcess failed "+e);
   owned.Add(h,r);return h;
  }
  public static Observation Read(IntPtr h,uint pid,ulong made,string expected) {
   Observation r;Need(owned.TryGetValue(h,out r),"registered independently retained query handle");
   r.ExpectedImage=expected;
   r.ReturnedPid=GetProcessId(h);r.PidError=Marshal.GetLastWin32Error();
   FT c,e,k,u;r.TimesReturned=GetProcessTimes(h,out c,out e,out k,out u);r.TimesError=Marshal.GetLastWin32Error();
   r.CreationFiletime=c.Value.ToString(CultureInfo.InvariantCulture);
   var image=new StringBuilder(32768);uint n=32768;r.ImageReturned=QueryFullProcessImageNameW(h,0,image,ref n);r.ImageError=Marshal.GetLastWin32Error();r.ReturnedLength=n;r.Image=image.ToString();
   Need(r.ReturnedPid==pid&&pid!=0,"independent query-H PID differs");
   Need(r.TimesReturned&&c.Value==made,"independent query-H full kernel creation differs");
   Need(r.ImageReturned&&n>0&&n<32768&&r.Image.Length==n&&String.Equals(r.Image,expected,StringComparison.OrdinalIgnoreCase),"independent query-H exact image differs");
   return r;
  }
  public static Observation CloseOwned(IntPtr h) {
   Observation r;Need(owned.TryGetValue(h,out r)&&!r.CloseAttempted,"new known query handle one close only");
   r.CloseAttempted=true;r.ClosedActual=CloseHandle(h);r.CloseError=Marshal.GetLastWin32Error();
   Need(r.ClosedActual,"independent query-H CloseHandle failed; retained registry, no retry");owned.Remove(h);return r;
  }
  public static Observation Observe(uint pid,ulong made,string expected) {
   IntPtr h=Acquire(pid,0x1000);Read(h,pid,made,expected);return CloseOwned(h);
  }
 }
}
