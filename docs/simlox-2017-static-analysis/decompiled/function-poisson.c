/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-poisson.json
 * Evidence: ev_5ce902d06e6fa5783d9dda0b5ff9b1a570d8648fba4e3161664f261ca27acb6e
 */


int FUN_140d8e770(double param_1,uint *param_2)

{
  double dVar1;
  int iVar2;
  uint uVar3;
  double dVar4;
  undefined8 uVar5;
  
  if (param_1 <= 0.0) {
    return 0;
  }
  if (param_1 <= 25.0) {
    iVar2 = 0;
    uVar3 = *param_2 * -0x373d8c6b & 0x7fffffff;
    *param_2 = uVar3;
    dVar4 = (double)FUN_1411a5520(SUB84(param_1,0));
    for (dVar1 = (double)uVar3 * 4.656612873077393e-10; dVar4 < dVar1;
        dVar1 = dVar1 * (double)uVar3 * 4.656612873077393e-10) {
      iVar2 = iVar2 + 1;
      uVar3 = uVar3 * -0x373d8c6b & 0x7fffffff;
      *param_2 = uVar3;
    }
  }
  else {
    uVar5 = FUN_1411a648c();
    dVar1 = (double)FUN_140d8e6c0(SUB84(param_1,0),uVar5,param_2);
    iVar2 = (int)dVar1;
    if (iVar2 < 0) {
      return 0;
    }
  }
  return iVar2;
}


