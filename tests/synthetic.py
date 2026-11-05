"""Data shared by the tests that build tiny DOLs by hand.

Datos compartidos por las pruebas que arman DOLs mínimos a mano.

The instructions come from tools/ppc_encode.py and the DOL file from
`dol.write_dol`; only what is specific to the tests is kept here.
"""

# The analysis needs an extab and an extabindex section to exist; one
# all-zero index entry is a valid "no exception tables" index.
EMPTY_EXCEPTION_SECTIONS = {
    0: (0x80006000, b"\0" * 8),  # extab
    1: (0x80006100, b"\0" * 12),  # extabindex
}
