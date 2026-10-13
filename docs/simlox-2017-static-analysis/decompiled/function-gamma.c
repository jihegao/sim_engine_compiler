/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-gamma.json
 * Evidence: ev_27ecca58c68d5367e94df9378bd52a029bff19de39502745f710f8c4f3385bf0
 */


double FUN_140d8e3d0(double param_1,double param_2,uint *param_3)

{
  double dVar1;
  uint uVar2;
  int iVar3;
  double dVar4;
  
  uVar2 = *param_3;
  iVar3 = 1;
  dVar1 = 0.0;
  dVar4 = 0.0;
  if (1.0 <= param_1) {
    do {
      uVar2 = uVar2 * -0x373d8c6b & 0x7fffffff;
      dVar4 = (double)uVar2 * 4.656612873077393e-10;
      if (iVar3 == 1) {
        *param_3 = uVar2;
      }
      if (dVar4 == 0.0) {
        dVar4 = dVar4 + 2.220446049250313e-16;
      }
      dVar4 = (double)FUN_1411a5990(dVar4);
      iVar3 = iVar3 + 1;
      dVar1 = dVar1 + dVar4;
      dVar4 = dVar1;
    } while ((double)iVar3 <= param_1);
  }
  return (-1.0 / param_2) * dVar4;
}


