/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-error-vector.json
 * Evidence: ev_df61d03c396448c2fe5923ada5a7b5ba92a297a498c6435e2d52c5ad5b0cdbbc
 */


undefined8 * FUN_140e5eff0(longlong param_1,undefined8 *param_2,undefined4 param_3)

{
  undefined8 uVar1;
  undefined8 uVar2;
  undefined8 uVar3;
  
  uVar2 = FUN_140e5e590(param_1,*(undefined8 *)(param_1 + 0xa0),*(undefined8 *)(param_1 + 0xc0),
                        param_3);
  uVar3 = *(undefined8 *)(param_1 + 200);
  uVar1 = *(undefined8 *)(param_1 + 0xa8);
  *param_2 = uVar2;
  uVar2 = FUN_140e5e590(param_1,uVar1,uVar3,param_3);
  uVar3 = *(undefined8 *)(param_1 + 0xd0);
  uVar1 = *(undefined8 *)(param_1 + 0xb0);
  param_2[1] = uVar2;
  uVar2 = FUN_140e5e590(param_1,uVar1,uVar3,param_3);
  uVar3 = *(undefined8 *)(param_1 + 0xd8);
  uVar1 = *(undefined8 *)(param_1 + 0xb8);
  param_2[2] = uVar2;
  uVar3 = FUN_140e5e590(param_1,uVar1,uVar3,param_3);
  param_2[3] = uVar3;
  return param_2;
}


