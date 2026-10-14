/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-mt19937.json
 * Evidence: ev_97ff84c3b5675c8c52be2a12fbf4148aff9705146757b4f55f5902620ab13457
 */


uint FUN_140ea9700(uint *param_1)

{
  uint uVar1;
  uint *puVar2;
  longlong lVar3;
  
  lVar3 = 0x270;
  if (*param_1 == 0x270) {
    puVar2 = param_1 + 2;
    do {
      uVar1 = (puVar2[-1] ^ *puVar2) & 0x7fffffff ^ puVar2[-1];
      puVar2[0x26f] = -(uint)((uVar1 & 1) != 0) & 0x9908b0df ^ puVar2[0x18c] ^ uVar1 >> 1;
      lVar3 = lVar3 + -1;
      puVar2 = puVar2 + 1;
    } while (lVar3 != 0);
  }
  else if (0x4df < *param_1) {
    FUN_140ea9920();
  }
  uVar1 = param_1[(ulonglong)*param_1 + 1];
  *param_1 = *param_1 + 1;
  uVar1 = uVar1 ^ param_1[0x4e1] & uVar1 >> 0xb;
  uVar1 = uVar1 ^ (uVar1 & 0xff3a58ad) << 7;
  uVar1 = uVar1 ^ (uVar1 & 0xffffdf8c) << 0xf;
  return uVar1 >> 0x12 ^ uVar1;
}


