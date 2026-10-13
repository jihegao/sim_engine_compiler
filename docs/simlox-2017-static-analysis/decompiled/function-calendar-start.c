/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-calendar-start.json
 * Evidence: ev_d8ab95336e5a82c1d56c9c0e912a48240421e80b7038f22ca8886db1916f1c33
 */


void FUN_140d8e9d0(longlong param_1,undefined4 param_2,undefined8 param_3,undefined8 param_4)

{
  void *pvVar1;
  longlong lVar2;
  undefined8 uVar3;
  
  uVar3 = 0xfffffffffffffffe;
  pvVar1 = operator_new(0x40);
  if (pvVar1 == (void *)0x0) {
    lVar2 = 0;
  }
  else {
    lVar2 = FUN_140d8dba0(pvVar1,param_1);
  }
  FUN_140d8ebb0(lVar2,param_2,0x80000000,param_4,uVar3);
  *(undefined8 *)(*(longlong *)(lVar2 + 0x30) + 0x28) = 0x41dfffffffc00000;
  *(longlong *)(param_1 + 8) = lVar2;
  FUN_140d8e8f0(param_1);
  return;
}


