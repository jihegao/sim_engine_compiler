using System;
namespace Issue18ContentIntegrityV1 {
 // Internal byte-computation utility only. The future owning pass must reserve
 // 128 payload bytes before construction. No lease, IO, terminal or seal proof.
 internal sealed class BoundedSha256 {
  internal const long MaximumBytes=67108864L;
  readonly byte[] block=new byte[64];
  readonly byte[] digest=new byte[32];
  readonly uint[] state=new uint[8] {
   0x6a09e667U,0xbb67ae85U,0x3c6ef372U,0xa54ff53aU,
   0x510e527fU,0x9b05688cU,0x1f83d9abU,0x5be0cd19U };
  readonly uint[] schedule=new uint[64];
  static readonly uint[] Round=new uint[64] {
   0x428a2f98U,0x71374491U,0xb5c0fbcfU,0xe9b5dba5U,0x3956c25bU,0x59f111f1U,0x923f82a4U,0xab1c5ed5U,
   0xd807aa98U,0x12835b01U,0x243185beU,0x550c7dc3U,0x72be5d74U,0x80deb1feU,0x9bdc06a7U,0xc19bf174U,
   0xe49b69c1U,0xefbe4786U,0x0fc19dc6U,0x240ca1ccU,0x2de92c6fU,0x4a7484aaU,0x5cb0a9dcU,0x76f988daU,
   0x983e5152U,0xa831c66dU,0xb00327c8U,0xbf597fc7U,0xc6e00bf3U,0xd5a79147U,0x06ca6351U,0x14292967U,
   0x27b70a85U,0x2e1b2138U,0x4d2c6dfcU,0x53380d13U,0x650a7354U,0x766a0abbU,0x81c2c92eU,0x92722c85U,
   0xa2bfe8a1U,0xa81a664bU,0xc24b8b70U,0xc76c51a3U,0xd192e819U,0xd6990624U,0xf40e3585U,0x106aa070U,
   0x19a4c116U,0x1e376c08U,0x2748774cU,0x34b0bcb5U,0x391c0cb3U,0x4ed8aa4aU,0x5b9cca4fU,0x682e6ff3U,
   0x748f82eeU,0x78a5636fU,0x84c87814U,0x8cc70208U,0x90befffaU,0xa4506cebU,0xbef9a3f7U,0xc67178f2U };
  long bytes;
  int used;
  bool finalized;
  internal long ProcessedBytes { get { return bytes; } }
  internal bool Finalized { get { return finalized; } }
  internal void Append(byte[] input,int start,int count) {
   if(finalized)throw new InvalidOperationException("hash already finalized");
   if(input==null)throw new ArgumentNullException("input");
   if(start<0||count<0||start>input.Length||count>input.Length-start)
    throw new ArgumentOutOfRangeException("hash slice");
   if(count>MaximumBytes-bytes)throw new InvalidOperationException("hash byte bound");
   // All rejection checks precede any byte or state mutation.
   int end=checked(start+count);
   for(int i=start;i<end;i++) {
    block[used++]=input[i]; bytes=checked(bytes+1L);
    if(used==64){Compress();used=0;}
   }
  }
  static uint Rotate(uint x,int n) { return (x>>n)|(x<<(32-n)); }
  void Compress() {
   unchecked {
    for(int i=0;i<16;i++) {
     int j=i*4;
     schedule[i]=((uint)block[j]<<24)|((uint)block[j+1]<<16)|((uint)block[j+2]<<8)|block[j+3];
    }
    for(int i=16;i<64;i++) {
     uint x=schedule[i-15],y=schedule[i-2];
     uint s0=Rotate(x,7)^Rotate(x,18)^(x>>3);
     uint s1=Rotate(y,17)^Rotate(y,19)^(y>>10);
     schedule[i]=schedule[i-16]+s0+schedule[i-7]+s1;
    }
    uint a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
    for(int i=0;i<64;i++) {
     uint s1=Rotate(e,6)^Rotate(e,11)^Rotate(e,25);
     uint ch=(e&f)^((~e)&g);
     uint t1=h+s1+ch+Round[i]+schedule[i];
     uint s0=Rotate(a,2)^Rotate(a,13)^Rotate(a,22);
     uint maj=(a&b)^(a&c)^(b&c);
     uint t2=s0+maj;
     h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;
    state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
   }
  }
  internal string FinishHex() {
   if(finalized)throw new InvalidOperationException("hash already finalized");
   ulong bits=checked((ulong)bytes*8UL);
   block[used++]=0x80;
   if(used>56) {
    while(used<64)block[used++]=0;
    Compress();used=0;
   }
   while(used<56)block[used++]=0;
   for(int i=7;i>=0;i--)block[used++]=unchecked((byte)(bits>>(8*i)));
   Compress();used=0;
   unchecked {
    for(int i=0;i<8;i++)for(int j=0;j<4;j++)digest[i*4+j]=(byte)(state[i]>>(24-j*8));
   }
   finalized=true;
   const string hex="0123456789abcdef";
   char[] result=new char[64];
   for(int i=0;i<32;i++){result[i*2]=hex[digest[i]>>4];result[i*2+1]=hex[digest[i]&15];}
   return new string(result);
  }
 }
}

