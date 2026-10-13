/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-exp-math.json
 * Evidence: ev_d3faa5f00aceacc41266649d0c2fa4fee40beb1abb3295861bf4dc40b29dfe74
 */


double FUN_140d8e640(double param_1,uint *param_2)

{
  uint uVar1;
  double dVar2;
  
  if (param_1 <= 0.0) {
    return 10000000000.0;
  }
  uVar1 = *param_2 * -0x373d8c6b & 0x7fffffff;
  *param_2 = uVar1;
  dVar2 = (double)FUN_1411a5990((double)uVar1 * 4.656612873077393e-10);
  return -(dVar2 / param_1);
}


