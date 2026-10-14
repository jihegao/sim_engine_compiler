/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-triangular.json
 * Evidence: ev_6f069bebe199a312e18fe3073ea3a92e3af8cb3c624d627fe03a1aa27ffeaee7
 */


double FUN_140d8eb10(double param_1,double param_2,double param_3,uint *param_4)

{
  uint uVar1;
  uint uVar2;
  double dVar3;
  double dVar4;
  
  uVar1 = *param_4 * -0x373d8c6b & 0x7fffffff;
  *param_4 = uVar1;
  uVar2 = uVar1 * -0x373d8c6b & 0x7fffffff;
  dVar3 = (double)uVar2 * 4.656612873077393e-10;
  dVar4 = (double)(uVar2 * -0x373d8c6b & 0x7fffffff) * 4.656612873077393e-10;
  if (dVar3 <= dVar4) {
    dVar3 = dVar4;
  }
  return (((param_2 - param_1) * (double)uVar1 * 4.656612873077393e-10 + param_1) - param_3) * dVar3
         + param_3;
}


