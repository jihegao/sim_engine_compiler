/* Ghidra-generated analysis pseudocode. Not original source; not a compilable reconstruction.
 * Response: function-event-order.json
 * Evidence: ev_1edeecc93bd83acf9cf89d8eb96d206a283fcdecde1f65b3c0b54e3f6a08b3da
 */


bool FUN_140d8ea60(longlong param_1,longlong param_2)

{
  if (*(double *)(param_1 + 0x18) < *(double *)(param_2 + 0x18)) {
    return true;
  }
  if (*(double *)(param_1 + 0x18) <= *(double *)(param_2 + 0x18)) {
    if (*(int *)(param_2 + 0x20) < *(int *)(param_1 + 0x20)) {
      return true;
    }
    if (*(int *)(param_2 + 0x20) <= *(int *)(param_1 + 0x20)) {
      return *(double *)(param_1 + 0x28) <= *(double *)(param_2 + 0x28) &&
             *(double *)(param_2 + 0x28) != *(double *)(param_1 + 0x28);
    }
  }
  return false;
}


