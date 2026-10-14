/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-boxmuller.json
 * Evidence: ev_436ab885cb65157bd69a90db84bb4f5af48cac007a1119a058bc7b595d1f7e16
 */


double FUN_140d8e6c0(double param_1,double param_2,uint *param_3)

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
  return dVar2 * param_2 * dVar3 + param_1;
}


