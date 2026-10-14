/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-lognormal.json
 * Evidence: ev_4a53e9519f7ec47c329c01c0a79dee1302d18741b36a61a592761f22488aeab4
 */


void FUN_140d8e550(double param_1,double param_2,uint *param_3)

{
  uint uVar1;
  double dVar2;
  double dVar3;
  
  uVar1 = *param_3 * -0x373d8c6b & 0x7fffffff;
  *param_3 = uVar1;
  dVar2 = (double)FUN_1411a5990((double)uVar1 * 4.656612873077393e-10);
  dVar2 = (double)FUN_1411a648c(dVar2 * -2.0);
  dVar3 = (double)FUN_1411a99f0((double)(uVar1 * -0x373d8c6b & 0x7fffffff) * 4.656612873077393e-10 *
                                6.283185307);
  FUN_1411a5520(dVar2 * param_2 * dVar3 + param_1);
  return;
}


