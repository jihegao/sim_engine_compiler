// Selected K02 vertical integration only. No execution authority is supplied by this source.
// Reuses the accepted x64 process ABI, quoting, explicit standard-handle list,
// fixed SHA utility, and terminal ownership rules. No generic/mock coordinator.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.ComponentModel;
using System.Threading;
using Microsoft.Win32.SafeHandles;
using Issue18ContentIntegrityV1;
namespace Issue18SelectedK02V4 {
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct SI {
  public uint cb;public IntPtr reserved,desktop,title;public uint x,y,xsize,ysize,xchars,ychars,fill,flags;public ushort show,reserved2;public IntPtr reservedPtr,input,output,error;
 }
 [StructLayout(LayoutKind.Sequential)] public struct SIX {public SI si;public IntPtr attributes;}
 [StructLayout(LayoutKind.Sequential)] public struct PI {public IntPtr process,thread;public uint pid,tid;}
 [StructLayout(LayoutKind.Sequential)] public struct FT {public uint low,high;public ulong Value{get{return ((ulong)high<<32)|low;}}}
 [StructLayout(LayoutKind.Sequential)] public struct INFO {
  public uint attributes;public FT creation,access,write;public uint volume,sizeHigh,sizeLow,links,idHigh,idLow;
  public ulong Id{get{return ((ulong)idHigh<<32)|idLow;}}public long Length{get{return checked((long)(((ulong)sizeHigh<<32)|sizeLow));}}
 }
 [StructLayout(LayoutKind.Sequential,Size=40)] internal struct BASIC {internal long creation,access,write,change;internal uint attributes;}
 internal static class K {
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool CreateProcessW(string app,StringBuilder cmd,IntPtr pa,IntPtr ta,[MarshalAs(UnmanagedType.Bool)]bool inherit,uint flags,IntPtr env,string cwd,ref SIX si,out PI pi);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool InitializeProcThreadAttributeList(IntPtr p,int n,uint f,ref UIntPtr s);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool UpdateProcThreadAttribute(IntPtr p,uint f,UIntPtr a,IntPtr v,UIntPtr n,IntPtr old,IntPtr returned);
  [DllImport("kernel32.dll")] internal static extern void DeleteProcThreadAttributeList(IntPtr p);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true)] internal static extern uint GetProcessId(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool GetProcessTimes(IntPtr h,out FT c,out FT e,out FT k,out FT u);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool ProcessIdToSessionId(uint p,out uint s);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool QueryFullProcessImageNameW(IntPtr p,uint f,StringBuilder b,ref uint n);
  [DllImport("kernel32.dll",SetLastError=true)] internal static extern uint ResumeThread(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true)] internal static extern uint WaitForSingleObject(IntPtr h,uint ms);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool GetExitCodeProcess(IntPtr h,out uint c);
  [DllImport("kernel32.dll")] internal static extern uint GetCurrentThreadId();
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool GetFileInformationByHandle(IntPtr h,out INFO i);
  [DllImport("kernel32.dll",SetLastError=true)] internal static extern uint GetFileType(IntPtr h);
  [DllImport("kernel32.dll",ExactSpelling=true,SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool GetFileInformationByHandleEx(IntPtr h,int infoClass,out uint flags,uint size);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,ExactSpelling=true,SetLastError=true)] internal static extern uint GetFinalPathNameByHandleW(IntPtr h,StringBuilder b,uint n,uint f);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool FlushFileBuffers(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool SetFileInformationByHandle(IntPtr h,int c,ref BASIC b,uint n);
  [DllImport("kernel32.dll",SetLastError=true)] [return:MarshalAs(UnmanagedType.Bool)] internal static extern bool SetHandleInformation(IntPtr h,uint mask,uint flags);
  [DllImport("ntdll.dll",ExactSpelling=true)] internal static extern int NtCreateFile(IntPtr h,uint access,IntPtr oa,IntPtr ios,IntPtr allocation,uint attributes,uint share,uint disposition,uint options,IntPtr ea,uint eaLength);
 }
 public sealed class Slot {
  public readonly string Role,Path;public readonly IntPtr H;public readonly long Generation;
  public bool CloseAttempted,ClosedActual,CloseUnknown;public int? CloseError;
  internal Slot(string r,string p,IntPtr h,long g){Role=r;Path=p;H=h;Generation=g;}
 }
 public sealed class Child {
  public string Stage,Application,Command,ImagePath;public uint Pid,Tid,Session,ResumeCount,ExitCode;public ulong Creation;
  public bool CreateAttempted,CreateReturned,Created,ResumeAttempted,ResumeReturned,Signaled,IdentityBeforeResume,IdentityAfterSignal,ExitCodeObserved;
  public int? CreateError,ResumeError,WaitError;internal Slot Process,Thread,Input,Output,Error;public string Failure;
 }
 public sealed class Pin {
  public string Name,Sha,Path;public long Bytes;public uint Volume,Attributes;public ulong Id,Creation;internal Slot Lease;
 }
 public sealed class Result {
  public string Version="1.0.4-selected-owner4",RunId,Mode,Failure;public bool Failed,RawOwned,RecoveredOwned,OriginalSealed,RecoveryVerified,RawBehaviorAccepted,QueueOwned,QueueReleaseAttempted,QueueReleasedActual,UnknownChild;
  public readonly List<Child> Children=new List<Child>();public readonly List<Slot> Handles=new List<Slot>();public readonly List<Pin> Originals=new List<Pin>();public readonly List<Pin> Recovered=new List<Pin>();
  public readonly List<string> Events=new List<string>();public int NativeSimloxCalls,SimulationCalls,ParentReruns;
 }
 public sealed class Config {
  public string Mode,RunId,Physical,Recovered,Review,WorkingDirectory,InputSource,InputSha,ExecutableSha;
 }
 public sealed class SelectedOwner {
  const string Workspace=@"C:\Users\user\Documents\Codex\2026-10-09\i05-var08-pm-location";
  const string Simlox=@"C:\Program Files\Systecon\SIMLOX\Simlox.exe";
  readonly Config c;readonly Result r=new Result();readonly uint thread;readonly Action<uint,ulong,uint> safety,identity;readonly Action<string> validator;
  readonly Dictionary<string,Slot> directories=new Dictionary<string,Slot>(StringComparer.OrdinalIgnoreCase);
  readonly List<IntPtr> allocations=new List<IntPtr>();Mutex queue;long generation;Slot raw,recovery,exeLease;string exe,trace;
  SelectedOwner(Config cfg,Action<uint,ulong,uint> fresh,Action<uint,ulong,uint> independent,Action<string> check){c=cfg;safety=fresh;identity=independent;validator=check;thread=K.GetCurrentThreadId();r.RunId=c.RunId;r.Mode=c.Mode;}
  static void Need(bool b,string why){if(!b)throw new InvalidOperationException(why);}
  static bool Valid(IntPtr h){return h!=IntPtr.Zero&&h!=new IntPtr(-1);}
  static Exception Win(string what,int e){return new Win32Exception(e,what);}
  public static string Quote(string s){if(s==null||s.IndexOf('\0')>=0||s.IndexOf('\r')>=0||s.IndexOf('\n')>=0)throw new ArgumentException("invalid argument");var b=new StringBuilder("\"");int slashes=0;foreach(char ch in s){if(ch=='\\'){slashes++;continue;}if(ch=='"'){b.Append('\\',slashes*2+1);b.Append(ch);}else{b.Append('\\',slashes);b.Append(ch);}slashes=0;}b.Append('\\',slashes*2);return b.Append('"').ToString();}
  public static void CheckAbi(){Need(IntPtr.Size==8&&BitConverter.IsLittleEndian&&Marshal.SizeOf(typeof(SI))==104&&Marshal.SizeOf(typeof(SIX))==112&&Marshal.SizeOf(typeof(PI))==24&&Marshal.SizeOf(typeof(INFO))==52&&Marshal.SizeOf(typeof(BASIC))==40,"selected x64 ABI");Need(Marshal.OffsetOf(typeof(SIX),"attributes").ToInt32()==104&&Marshal.OffsetOf(typeof(PI),"pid").ToInt32()==16&&Marshal.OffsetOf(typeof(INFO),"volume").ToInt32()==28&&Marshal.OffsetOf(typeof(BASIC),"attributes").ToInt32()==32,"selected ABI offsets");}
  void Emit(string s){r.Events.Add(DateTime.UtcNow.ToString("o")+" "+s);File.AppendAllText(trace,r.Events[r.Events.Count-1]+Environment.NewLine,new UTF8Encoding(false));}
  void Failed(Exception e){r.Failed=true;if(r.Failure==null)r.Failure=e.ToString();try{Emit("NO_GO "+e.Message);}catch{}}
  void Hold(string why){Failed(new InvalidOperationException("OWNERSHIP_HELD_NO_KILL_RETRY_RELEASE "+why));try{Console.Error.WriteLine(r.Failure);}catch{}while(true){GC.KeepAlive(this);Thread.Sleep(1000);}}
  void SameThread(){Need(K.GetCurrentThreadId()==thread,"same synchronous OS owner thread");}
  Slot Register(string role,string path,IntPtr h){Need(Valid(h),"actual valid H");foreach(var s in r.Handles)if(!s.ClosedActual&&s.H==h)Hold("active H alias");var x=new Slot(role,path,h,++generation);r.Handles.Add(x);return x;}
  void Close(Slot s){if(s==null||s.ClosedActual)return;SameThread();if(s.CloseAttempted)Hold("unconfirmed close no retry "+s.Role);s.CloseAttempted=true;bool ok=false;try{ok=K.CloseHandle(s.H);int e=Marshal.GetLastWin32Error();s.CloseError=e;s.ClosedActual=ok;s.CloseUnknown=!ok;}catch{s.CloseUnknown=true;Hold("close exception "+s.Role);}if(!ok)Hold("close false "+s.Role);Emit("CLOSED_ACTUAL "+s.Role+" "+s.Generation);}
  IntPtr Alloc(int size){IntPtr p=Marshal.AllocHGlobal(size);allocations.Add(p);for(int i=0;i<size;i++)Marshal.WriteByte(p,i,0);return p;}
  void FreeKnown(IntPtr p){Marshal.FreeHGlobal(p);allocations.Remove(p);}
  static void Leaf(string n){Need(!String.IsNullOrEmpty(n)&&n!="."&&n!=".."&&n.Length<=120&&n[0]!='.'&&n[n.Length-1]!='.',"one bounded leaf");foreach(char x in n)Need(Char.IsLetterOrDigit(x)&&x<128||x=='-'||x=='_'||x=='.',"ASCII leaf");string stem=n.Split('.')[0].ToUpperInvariant();Need(stem!="CON"&&stem!="NUL"&&stem!="PRN"&&stem!="AUX"&&!(stem.Length==4&&(stem.StartsWith("COM")||stem.StartsWith("LPT"))&&stem[3]>='1'&&stem[3]<='9'),"not device leaf");}
  Slot Open(string role,Slot parent,string name,string expectedPath,uint access,uint share,uint disposition,uint options,uint attributes){
   SameThread();if(parent!=null){Need(!String.IsNullOrEmpty(name)&&name!="."&&name!=".."&&name.Length<=120&&name[name.Length-1]!='.'&&name[name.Length-1]!=' ',"one bounded native component");foreach(char ch in name)Need(ch>=32&&ch<127&&"\\/:*?\"<>|".IndexOf(ch)<0,"literal native component");}byte[] utf=Encoding.Unicode.GetBytes(name);Need(utf.Length<=240,"bounded native name");
   int start=allocations.Count;IntPtr hn=Alloc(8),ios=Alloc(16),str=Alloc(utf.Length+2),us=Alloc(16),oa=Alloc(48);Marshal.WriteIntPtr(hn,new IntPtr(-1));Marshal.Copy(utf,0,str,utf.Length);Marshal.WriteInt16(us,0,checked((short)utf.Length));Marshal.WriteInt16(us,2,checked((short)(utf.Length+2)));Marshal.WriteIntPtr(us,8,str);Marshal.WriteInt32(oa,0,48);Marshal.WriteIntPtr(oa,8,parent==null?IntPtr.Zero:parent.H);Marshal.WriteIntPtr(oa,16,us);Marshal.WriteInt32(oa,24,0x40);
   int status;try{status=K.NtCreateFile(hn,access,oa,ios,IntPtr.Zero,attributes,share,disposition,options,IntPtr.Zero,0);}catch{Hold("NtCreate unavailable; retained request memory/parent");return null;}
   IntPtr actual=Marshal.ReadIntPtr(hn);int actualIos=Marshal.ReadInt32(ios);ulong info=unchecked((ulong)Marshal.ReadInt64(ios,8));Slot slot=Valid(actual)?Register(role,expectedPath,actual):null;
   try{Emit("NT_CREATE_RETURN role="+role+" status="+status+" statusHex="+unchecked((uint)status).ToString("x8")+" ios="+actualIos+" iosHex="+unchecked((uint)actualIos).ToString("x8")+" information="+info+" actualH="+actual+" validH="+Valid(actual)+" registered="+(slot!=null)+" parentH="+(parent==null?IntPtr.Zero:parent.H)+" name="+name+" expectedPath="+expectedPath+" access="+access+" share="+share+" disposition="+disposition+" options="+options+" attributes="+attributes);}catch{Hold("NtCreate returned tuple logging unavailable; actual H/scratch/parent retained");}
   if(status==0x103||actualIos==0x103)Hold("pending NtCreate memory/actual H retained");
   if(status!=0){if(slot!=null)Hold("failed NtCreate returned actual H");for(int i=allocations.Count-1;i>=start;i--)FreeKnown(allocations[i]);Emit("NT_CREATE_REJECTED "+role+" status="+status+" ios="+actualIos+" info="+info+" H="+actual);throw new InvalidOperationException("NtCreate failed literal status "+status);}
   if(slot==null||actualIos!=0||info!=(disposition==2?2UL:1UL))Hold("success NtCreate output/IOS binding");
   for(int i=allocations.Count-1;i>=start;i--)FreeKnown(allocations[i]);Emit("NT_CREATE "+role+" status="+status+" ios="+actualIos+" info="+info+" H="+actual+" parent="+(parent==null?IntPtr.Zero:parent.H)+" name="+name+" access="+access+" share="+share+" disposition="+disposition+" options="+options);return slot;
  }
  INFO Meta(Slot s,bool directory){INFO a;bool ok=K.GetFileInformationByHandle(s.H,out a);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("actual file metadata "+s.Path,e);uint type=K.GetFileType(s.H);int te=Marshal.GetLastWin32Error();Need(type==1,"disk file type "+te);Need((a.attributes&0x400)==0&&((a.attributes&16)!=0)==directory&&a.Id!=0&&a.links>0,"nonreparse expected file identity");if(!directory)Need((a.links==1||s.Path==exe)&&a.Length>=0&&a.Length<=67108864,"selected bounded file; only the pinned executable may have OS hardlinks");return a;}
  string Final(Slot s){var b=new StringBuilder(32768);uint n=K.GetFinalPathNameByHandleW(s.H,b,32768,1);int e=Marshal.GetLastWin32Error();if(n==0||n>=32768)throw Win("final GUID path",e);return b.ToString();}
  // Candidate classification only; no OS-query result is inferred here.
  internal static int RelativeLeafMode(string parentFinal,string actualFinal,string requested){
   if(parentFinal==null||actualFinal==null||String.IsNullOrEmpty(requested))return 0;
   string prefix=parentFinal.TrimEnd('\\')+"\\";
   if(!actualFinal.StartsWith(prefix,StringComparison.Ordinal))return 0;
   string leaf=actualFinal.Substring(prefix.Length);
   if(leaf.Length==0||leaf.Length>120||leaf.Length!=requested.Length||leaf.IndexOf('\\')>=0||leaf.IndexOf('/')>=0)return 0;
   if(leaf==requested)return 1;
   for(int i=0;i<leaf.Length;i++){
    char a=leaf[i],z=requested[i];if(a<32||a>=127||z<32||z>=127)return 0;
    if(a>='A'&&a<='Z')a=(char)(a+('a'-'A'));
    if(z>='A'&&z<='Z')z=(char)(z+('a'-'A'));
    if(a!=z)return 0;
   }
   return 2;
  }
  void RelativeAncestor(Slot parent,Slot child,string requested){
   string parentFinal=Final(parent),actualFinal=Final(child);
   int mode=RelativeLeafMode(parentFinal,actualFinal,requested);
   Need(mode!=0,"relative ancestor exact GUID parent and single ASCII leaf");
   if(mode==1)return;
   uint flags;bool ok=K.GetFileInformationByHandleEx(parent.H,23,out flags,4);int error=Marshal.GetLastWin32Error();
   Emit("CASE_QUERY parentH="+parent.H+" generation="+parent.Generation+" BOOL="+ok+" cachedError="+error+" rawFlags="+flags+" successfulFlagsAvailable="+ok);
   if(!ok)throw Win("actual parent directory case-sensitivity query",error);
   Need(flags==0,"case-only ancestor requires actual case-insensitive parent flags0");
   INFO pm=Meta(parent,true),cm=Meta(child,true);
   Need(pm.volume==cm.volume,"relative ancestor same actual volume");
   Emit("CANONICAL_CASE_ALIAS parentH="+parent.H+" parentGeneration="+parent.Generation+" childH="+child.H+" childGeneration="+child.Generation+" requestedLeaf="+requested+" parentGuid="+parentFinal+" childGuid="+actualFinal+" parentVolume="+pm.volume+" parentId="+pm.Id+" parentCreation="+pm.creation.Value+" childVolume="+cm.volume+" childId="+cm.Id+" childCreation="+cm.creation.Value+" flags="+flags+" mismatchAccepted=True");
  }
  Slot LockDirectory(string path){path=Path.GetFullPath(path).TrimEnd('\\');Slot found;if(directories.TryGetValue(path,out found))return found;
   string root=Path.GetPathRoot(path),cursor=root;Slot p;if(!directories.TryGetValue(root.TrimEnd('\\'),out p)){p=Open("Root",null,@"\??\"+root,root,0x1000A1,3,1,0x200021,0);Meta(p,true);string f=Final(p);Need(f.StartsWith(@"\\?\Volume{",StringComparison.Ordinal)&&f.EndsWith(@"}\",StringComparison.Ordinal),"actual volume GUID root");directories.Add(root.TrimEnd('\\'),p);}
   foreach(string leaf in path.Substring(root.Length).Split('\\')){if(leaf.Length==0)continue;cursor=Path.Combine(cursor,leaf);if(directories.TryGetValue(cursor,out found)){p=found;continue;}Slot parent=p;p=Open("Ancestor",parent,leaf,cursor,0x1000A1,3,1,0x200021,0);Meta(p,true);RelativeAncestor(parent,p,leaf);directories.Add(cursor,p);}return p;
  }
  Slot NewDirectory(string path){Need(!Directory.Exists(path)&&!File.Exists(path),"unique unoccupied directory");Slot p=LockDirectory(Path.GetDirectoryName(path));string name=Path.GetFileName(path);var s=Open("NewDirectory",p,name,path,0x1000A1,3,2,0x200021,0);Meta(s,true);Need(Final(s)==Final(p).TrimEnd('\\')+"\\"+name,"actual new directory provenance");directories.Add(path,s);return s;}
  Slot FileOpen(Slot dir,string name,uint access,uint share,uint disposition,uint attrs){var s=Open("File",dir,name,Path.Combine(dir.Path,name),access,share,disposition,0x200060,attrs);Meta(s,false);Need(Final(s)==Final(dir).TrimEnd('\\')+"\\"+name,"relative actual file path");return s;}
  FileStream Stream(Slot s,FileAccess access){return new FileStream(new SafeFileHandle(s.H,false),access,65536,false);}
  string Hash(Slot s){var hash=new BoundedSha256();byte[] b=new byte[65536];long total=0;using(var stream=Stream(s,FileAccess.Read)){stream.Seek(0,SeekOrigin.Begin);int n;while((n=stream.Read(b,0,b.Length))!=0){total=checked(total+n);Need(total<=67108864,"selected hash byte bound");hash.Append(b,0,n);}}return hash.FinishHex();}
  static bool Same(INFO a,INFO b){return a.volume==b.volume&&a.Id==b.Id&&a.creation.Value==b.creation.Value&&a.Length==b.Length&&a.links==b.links;}
  void Flush(Slot s){bool ok=K.FlushFileBuffers(s.H);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("flush same write H",e);}
  void Readonly(Slot s,uint target){BASIC b=new BASIC();b.attributes=target;bool ok=K.SetFileInformationByHandle(s.H,0,ref b,40);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("readonly same write H",e);Need(Meta(s,false).attributes==target,"actual readonly attribute");}
  Slot Handoff(Slot dir,string name,Slot writer,INFO before){
   var bridge=FileOpen(dir,name,0x100080,3,1,0);Need(Same(before,Meta(bridge,false)),"same family bridge");Close(writer);var strict=FileOpen(dir,name,0x100081,1,1,0);Need(Same(before,Meta(strict,false)),"same family strict");Close(bridge);return strict;
  }
  string[] Names(Slot dir){var all=Directory.GetFileSystemEntries(dir.Path);Need(all.Length<=32,"selected flat set size");var names=new List<string>();foreach(string p in all){string name=Path.GetFileName(p);Leaf(name);Need(!Directory.Exists(p),"no subdirectory in selected raw set");names.Add(name);}names.Sort(StringComparer.Ordinal);return names.ToArray();}
  static bool Equal(string[] a,string[] b){if(a.Length!=b.Length)return false;for(int i=0;i<a.Length;i++)if(a[i]!=b[i])return false;return true;}
  void CopyBytes(Slot source,Slot dest){byte[] b=new byte[65536];long total=0;using(var a=Stream(source,FileAccess.Read))using(var z=Stream(dest,FileAccess.Write)){a.Seek(0,SeekOrigin.Begin);z.Seek(0,SeekOrigin.Begin);int n;while((n=a.Read(b,0,b.Length))!=0){total=checked(total+n);Need(total<=67108864,"selected copy bound");z.Write(b,0,n);}z.Flush(true);}}
  void SealAndRecover(){
   string[] names=Names(raw);Need(names.Length>0,"actual partial/raw inventory");
   var allowed=new HashSet<string>(StringComparer.Ordinal);foreach(string n in c.Mode=="native"?new[]{"input.json","model.sxi","roundtrip-raw.json","import.log","export.log","jimport_save-stdout.bin","jimport_save-stderr.bin","jexport-stdout.bin","jexport-stderr.bin"}:new[]{"child.marker","probe-stdout.bin","probe-stderr.bin"})allowed.Add(n);
   foreach(string name in names){Need(allowed.Contains(name),"unexpected actual raw leaf "+name);var query=FileOpen(raw,name,0x100080,3,1,0);var before=Meta(query,false);Need(before.attributes==1||before.attributes==33||before.attributes==32||before.attributes==128,"bounded original attrs");Slot f;
    if((before.attributes&1)!=0){f=FileOpen(raw,name,0x100081,1,1,0);Need(Same(before,Meta(f,false)),"already-readonly original identity");Close(query);}
    else{f=FileOpen(raw,name,0x100183,1,1,0);Need(Same(before,Meta(f,false)),"original finalizer identity");Close(query);string prior=Hash(f);Flush(f);Readonly(f,before.attributes==32?33U:1U);Flush(f);Need(Same(before,Meta(f,false))&&Hash(f)==prior,"original unchanged through readonly");f=Handoff(raw,name,f,before);}
    var a=Meta(f,false);string sha=Hash(f);Need((a.attributes&1)!=0&&Same(before,a),"strict original seal");r.Originals.Add(new Pin{Name=name,Path=f.Path,Bytes=a.Length,Sha=sha,Volume=a.volume,Id=a.Id,Creation=a.creation.Value,Attributes=a.attributes,Lease=f});}
   Need(Equal(names,Names(raw)),"original exact complete set");r.OriginalSealed=true;Emit("ORIGINAL_SEALED "+names.Length);
   recovery=NewDirectory(c.Recovered);r.RecoveredOwned=true;Need(Names(recovery).Length==0,"actual recovered empty set");
   foreach(var p in r.Originals){var d=FileOpen(recovery,p.Name,0x100183,1,2,128);INFO birth=Meta(d,false);Need(birth.Length==0&&(birth.volume!=p.Volume||birth.Id!=p.Id),"exclusive distinct destination");CopyBytes(p.Lease,d);Flush(d);Readonly(d,p.Attributes);Flush(d);var actual=Meta(d,false);Need(actual.Length==p.Bytes&&Hash(d)==p.Sha,"destination exact byte/hash readback");d=Handoff(recovery,p.Name,d,actual);actual=Meta(d,false);r.Recovered.Add(new Pin{Name=p.Name,Path=d.Path,Bytes=actual.Length,Sha=Hash(d),Volume=actual.volume,Id=actual.Id,Creation=actual.creation.Value,Attributes=actual.attributes,Lease=d});}
   Need(Equal(names,Names(raw))&&Equal(names,Names(recovery)),"exact final original/recovery sets");
   for(int i=0;i<r.Originals.Count;i++){var a=r.Originals[i];var d=r.Recovered[i];INFO am=Meta(a.Lease,false),dm=Meta(d.Lease,false);Need(am.volume==a.Volume&&am.Id==a.Id&&am.creation.Value==a.Creation&&am.Length==a.Bytes&&(am.attributes&1)!=0&&Hash(a.Lease)==a.Sha,"final retained original");Need(dm.volume==d.Volume&&dm.Id==d.Id&&dm.creation.Value==d.Creation&&dm.Length==a.Bytes&&(dm.attributes&1)!=0&&Hash(d.Lease)==a.Sha,"final retained recovered");}
   r.RecoveryVerified=true;Emit("EXACT_RECOVERY_VERIFIED");
  }
  void Identity(Child child){FT made,exited,kernel,user;bool ok=K.GetProcessTimes(child.Process.H,out made,out exited,out kernel,out user);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("same original process creation",e);uint pid=K.GetProcessId(child.Process.H);int pe=Marshal.GetLastWin32Error();Need(pid==child.Pid&&pid!=0,"same original H pid "+pe);
   if(child.Signaled){Need(child.IdentityBeforeResume&&child.Creation==made.Value,"same retained original H identity after signal");return;}
   uint session;ok=K.ProcessIdToSessionId(pid,out session);e=Marshal.GetLastWin32Error();if(!ok)throw Win("session",e);Need(session==0,"native session0");var path=new StringBuilder(32768);uint size=32768;ok=K.QueryFullProcessImageNameW(child.Process.H,0,path,ref size);e=Marshal.GetLastWin32Error();if(!ok)throw Win("same-H image path",e);Need(String.Equals(path.ToString(),exe,StringComparison.OrdinalIgnoreCase),"exact native image");child.Creation=made.Value;child.Session=session;child.ImagePath=path.ToString();}
  void PhysicalInput(){if(c.Mode!="native")return;var input=FileOpen(raw,"input.json",0x100081,1,1,0);Need(Hash(input)==c.InputSha,"physical input exact before/after native stage");Close(input);}
  void Wait(Child child){while(!child.Signaled){uint status;try{status=K.WaitForSingleObject(child.Process.H,1000);int e=Marshal.GetLastWin32Error();if(status==0){child.Signaled=true;break;}if(status==258)continue;child.WaitError=e;Failed(new InvalidOperationException("wait observation "+status+" "+e));}catch(Exception e){Failed(e);}Thread.Sleep(1000);}}
  bool RunChild(string name,string command){
   var child=new Child{Stage=name,Application=exe,Command=command};r.Children.Add(child);
   IntPtr attrs=IntPtr.Zero,list=IntPtr.Zero;bool attrReady=false;PI pi=new PI();
   // NUL is an explicit native device, not imported as an ordinary evidence file.
   try{
    safety(0,0,0);PhysicalInput();Need(Hash(exeLease)==c.ExecutableSha,"executable unchanged before child");
    child.Input=Open("Input:NUL",null,@"\??\NUL","NUL",0x100081,3,1,0x20,0);
    child.Output=FileOpen(raw,name+"-stdout.bin",0x100182,1,2,128);child.Error=FileOpen(raw,name+"-stderr.bin",0x100182,1,2,128);
    foreach(var s in new[]{child.Input,child.Output,child.Error}){bool ok=K.SetHandleInformation(s.H,1,1);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("explicit inherited std H",e);}
    UIntPtr size=UIntPtr.Zero;bool query=K.InitializeProcThreadAttributeList(IntPtr.Zero,1,0,ref size);int err=Marshal.GetLastWin32Error();Need(!query&&err==122&&size.ToUInt64()>0&&size.ToUInt64()<=65536,"attribute-list size query");attrs=Alloc((int)size.ToUInt64());bool ready=K.InitializeProcThreadAttributeList(attrs,1,0,ref size);err=Marshal.GetLastWin32Error();if(!ready)throw Win("attribute init",err);attrReady=true;
    list=Alloc(24);Marshal.WriteIntPtr(list,0,child.Input.H);Marshal.WriteIntPtr(list,8,child.Output.H);Marshal.WriteIntPtr(list,16,child.Error.H);bool updated=K.UpdateProcThreadAttribute(attrs,0,new UIntPtr(0x20002),list,new UIntPtr(24),IntPtr.Zero,IntPtr.Zero);err=Marshal.GetLastWin32Error();if(!updated)throw Win("explicit3H list",err);
    SIX si=new SIX();si.si.cb=112;si.si.flags=0x101;si.si.show=0;si.si.input=child.Input.H;si.si.output=child.Output.H;si.si.error=child.Error.H;si.attributes=attrs;Emit("FROZEN_CREATE_SUSPENDED "+name+" "+command);
    child.CreateAttempted=true;
    bool success=false;try{success=K.CreateProcessW(exe,new StringBuilder(command),IntPtr.Zero,IntPtr.Zero,true,0x80004,IntPtr.Zero,c.WorkingDirectory,ref si,out pi);child.Created=success;child.CreateError=Marshal.GetLastWin32Error();child.CreateReturned=true;if(success&&c.Mode=="native")r.NativeSimloxCalls++;}finally{child.Pid=pi.pid;child.Tid=pi.tid;if(Valid(pi.process))child.Process=Register("Process:"+name,null,pi.process);if(Valid(pi.thread))child.Thread=Register("Thread:"+name,null,pi.thread);}
    if(!success){if(child.Process!=null||child.Thread!=null||pi.pid!=0||pi.tid!=0){r.UnknownChild=true;Hold("failed Create returned PI");}throw Win("CreateProcessW failed",child.CreateError.Value);}
    if(child.Process==null||child.Thread==null||child.Pid==0||child.Tid==0){r.UnknownChild=true;Hold("success missing original PI");}
    Identity(child);identity(child.Pid,child.Creation,child.Session);safety(child.Pid,child.Creation,child.Session);Need(Hash(exeLease)==c.ExecutableSha,"preResume executable hash");child.IdentityBeforeResume=true;Emit("IDENTITY_BEFORE_RESUME "+name+" "+child.Pid+" "+child.Creation+" "+child.Session);
    child.ResumeAttempted=true;child.ResumeCount=K.ResumeThread(child.Thread.H);child.ResumeError=Marshal.GetLastWin32Error();child.ResumeReturned=true;Need(child.ResumeCount==1,"single original Resume count");
   }catch(Exception e){child.Failure=e.ToString();Failed(e);if(child.CreateAttempted&&!child.CreateReturned){r.UnknownChild=true;Hold("Create transport unavailable");}}
   if(child.Created){Wait(child);try{Identity(child);child.IdentityAfterSignal=true;uint code;bool ok=K.GetExitCodeProcess(child.Process.H,out code);int e=Marshal.GetLastWin32Error();if(!ok)throw Win("exit after original H signal",e);child.ExitCode=code;child.ExitCodeObserved=true;Emit("ORIGINAL_H_SIGNALED "+name+" exit="+code);if(code!=0)Failed(new InvalidOperationException("child nonzero exit "+code));if(c.Mode=="native")Need(Meta(child.Error,false).Length==0,"native stderr must be empty");}catch(Exception e){Failed(e);}}
   // No cleanup ever precedes the SAME original-H signal of a created child.
   if(child.Created&&!child.Signaled)Hold("original H not signaled");
   Close(child.Input);Close(child.Output);Close(child.Error);
   if(attrReady){K.DeleteProcThreadAttributeList(attrs);attrReady=false;}if(attrs!=IntPtr.Zero)FreeKnown(attrs);if(list!=IntPtr.Zero)FreeKnown(list);
   if(child.Created){try{safety(0,0,0);PhysicalInput();}catch(Exception e){Failed(e);}}
   return !r.Failed;
  }
  void Validate(){
   CheckAbi();Need(c!=null&&safety!=null&&identity!=null,"mandatory bound config and guards");Need(c.Mode=="native"||c.Mode=="probe0"||c.Mode=="probe7","selected modes");Need(!String.IsNullOrEmpty(c.RunId)&&c.RunId.IndexOfAny(new[]{'\\','/','\r','\n'})<0,"run identity");foreach(string path in new[]{c.Physical,c.Recovered,c.Review,c.WorkingDirectory})Need(Path.IsPathRooted(path)&&Path.GetFullPath(path)==path,"canonical selected path");
   Need(c.Physical.StartsWith(Workspace+@"\tmp\k02-",StringComparison.Ordinal)&&c.Recovered.StartsWith(Workspace+@"\cases\simlox-air-support\K02-var01-json-dtim-precision-v1.0.4\",StringComparison.Ordinal),"selected K02 new paths");Need(c.Physical!=c.Recovered&&!c.Recovered.StartsWith(c.Physical+"\\",StringComparison.Ordinal)&&!c.Physical.StartsWith(c.Recovered+"\\",StringComparison.Ordinal),"distinct recovery");
   Need(!Directory.Exists(c.Physical)&&!File.Exists(c.Physical)&&!Directory.Exists(c.Recovered)&&!File.Exists(c.Recovered),"one-shot unused run paths");Need(Directory.Exists(c.Review),"external review directory");trace=Path.Combine(c.Review,"selected-owner-"+c.RunId+".log");using(var log=new FileStream(trace,FileMode.CreateNew,FileAccess.Write,FileShare.Read)){log.Flush(true);}exe=c.Mode=="native"?Simlox:Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System),"cmd.exe");Need(c.ExecutableSha!=null&&c.ExecutableSha.Length==64,"executable pin");
   if(c.Mode=="native")Need(c.InputSource==Workspace+@"\cases\simlox-air-support\K02-var01-json-dtim-precision-v1.0.4\native-input.json"&&c.InputSha=="178b4230dc6264de739320bd044dd389424609be27603555dee177bdd33a3e99"&&c.ExecutableSha=="fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"&&c.WorkingDirectory==@"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace"&&validator!=null,"exact selected native source/app/working-directory/validator");
  }
  Result Run(){
   Validate();SameThread();queue=new Mutex(false,@"Global\SimloxIssue18NativeQueue");try{r.QueueOwned=queue.WaitOne(0);}catch(AbandonedMutexException){r.QueueOwned=true;Hold("abandoned NativeQueue");}Need(r.QueueOwned,"NativeQueue occupied");
   try{
    safety(0,0,0);exeLease=FileOpen(LockDirectory(Path.GetDirectoryName(exe)),Path.GetFileName(exe),0x100081,1,1,0);Need(Hash(exeLease)==c.ExecutableSha,"exact executable");raw=NewDirectory(c.Physical);r.RawOwned=true;Need(Names(raw).Length==0,"fresh actual raw empty");
    if(c.Mode=="native"){
     var src=FileOpen(LockDirectory(Path.GetDirectoryName(c.InputSource)),Path.GetFileName(c.InputSource),0x100081,1,1,0);Need(Hash(src)==c.InputSha,"immutable source");var input=FileOpen(raw,"input.json",0x100183,1,2,128);CopyBytes(src,input);Need(Hash(input)==c.InputSha,"exact physical input");Close(input);
     string ip=Path.Combine(c.Physical,"input.json"),sxi=Path.Combine(c.Physical,"model.sxi"),op=Path.Combine(c.Physical,"roundtrip-raw.json");
     string command=Quote(exe)+" -silent -jimport "+Quote(ip)+" -save "+Quote(sxi)+" -log "+Quote(Path.Combine(c.Physical,"import.log"))+" -close";
     if(RunChild("jimport_save",command)){
      var model=FileOpen(raw,"model.sxi",0x100081,3,1,0);string before=Hash(model);Close(model);safety(0,0,0);
      command=Quote(exe)+" "+Quote(sxi)+" -silent -jexport "+Quote(op)+" -log "+Quote(Path.Combine(c.Physical,"export.log"))+" -close";RunChild("jexport",command);
      model=FileOpen(raw,"model.sxi",0x100081,1,1,0);Need(Hash(model)==before,"SXI unchanged across export");Close(model);
     }
    }else{
     int code=c.Mode=="probe0"?0:7;string marker=Path.Combine(c.Physical,"child.marker");Need(marker.IndexOfAny(new[]{'"','&','|','<','>','^','%','!'})<0,"exact harmless cmd path");
     string command=Quote(exe)+" /d /s /c \"(echo issue18-marker-"+code+")>"+Quote(marker)+"&(echo issue18-"+(code==0?"stdout-0)":"stderr-7)1>&2")+"&exit /b "+code+"\"";RunChild("probe",command);
    }
   }catch(Exception e){Failed(e);foreach(var child in r.Children)if(child.Created&&!child.Signaled)Wait(child);if(r.UnknownChild)Hold("unknown child ownership");}
   foreach(var child in r.Children)if(child.Created&&!child.Signaled)Hold("terminal original process predicate");
   try{if(r.RawOwned)SealAndRecover();}catch(Exception e){Failed(e);Hold("seal/copy incomplete, no automatic resource release");}
   if(c.Mode=="native"&&!r.Failed){try{Need(r.Originals.Count==9,"complete native nine-file raw inventory");validator(c.Physical);r.RawBehaviorAccepted=true;Emit("RAW_BEHAVIOR_VALIDATOR_RETURNED");}catch(Exception e){Failed(e);}}
   if(r.RawOwned)Need(r.OriginalSealed&&r.RecoveryVerified,"terminal exact original/recovery");
   for(int i=r.Handles.Count-1;i>=0;i--)Close(r.Handles[i]);
   Need(allocations.Count==0,"all known scratch closed before queue");SameThread();r.QueueReleaseAttempted=true;try{queue.ReleaseMutex();r.QueueReleasedActual=true;r.QueueOwned=false;queue.Dispose();}catch(Exception e){Failed(e);Hold("queue release unavailable");}return r;
  }
  public static Result Execute(Config cfg,Action<uint,ulong,uint> safety,Action<uint,ulong,uint> independentIdentity,Action<string> rawValidator){var owner=new SelectedOwner(cfg,safety,independentIdentity,rawValidator);try{return owner.Run();}catch(Exception e){owner.Failed(e);if(owner.r.QueueOwned&&!owner.r.QueueReleasedActual)owner.Hold("unhandled owning-stack failure");throw;}}
 }
}

