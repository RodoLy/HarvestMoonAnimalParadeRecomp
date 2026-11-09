// Checks that a WiiCompiled with patches/wiicompiled/foreign-game-addresses.patch reads the layer that
// tools/export_wiicompiled_layer.py writes. tests/test_foreign_game_patch.py builds and runs it.
//
// Comprueba que un WiiCompiled parchado lee la capa que escribe tools/export_wiicompiled_layer.py.
// Lo compila y corre tests/test_foreign_game_patch.py.

#include "guest_abi/guest_region.h"

#include <cstdio>
#include <cstdlib>

extern "C" const uint8_t kMkwGuestRegion = static_cast<uint8_t>(GuestRegion::Id::ForeignGame);

namespace GuestRegion {
// The runtime's own version aborts; this one says which address it was, for the test to read.
void FatalUnknownAddress(uint32_t pal) noexcept {
    std::printf("unknown %08X\n", pal);
    std::exit(3);
}
} // namespace GuestRegion

using GuestRegion::Id;
using GuestRegion::RowOf;

// Known at compile time: a native (OSSleepThread), a variable (DefaultThread), and a constant of
// Mario Kart Wii's EGG engine that this game does not have.
static_assert(RowOf(0x801AA9B8u).In(Id::ForeignGame) == 0x8025B8A0u, "OSSleepThread");
static_assert(RowOf(0x80347498u).In(Id::ForeignGame) == 0x8060D878u, "DefaultThread");
static_assert(RowOf(0x80388DD0u).In(Id::ForeignGame) == 0u, "EGG's fog constant has no address here");
// The three regions of Mario Kart Wii are untouched.
static_assert(RowOf(0x801AA9B8u).In(Id::Pal) == 0x801AA9B8u, "PAL");

int main() {
    const GuestRegion::Facts& facts = GuestRegion::CurrentFacts();
    std::printf("game %s\n", facts.gameId);
    std::printf("arena %08X\n", facts.mem1ArenaLo);
    std::printf("addresses %zu\n", GuestRegion::kForeignAddressCount);
    std::printf("sleep %08X\n", MKW_GADDR(801AA9B8));
    std::printf("egg registration %08X\n", GuestRegion::TranslateRegistration(0x8020FF9Cu));
    (void)MKW_GADDR(80388DD0);  // stops here: the game has no such constant
    std::printf("not reached\n");
    return 0;
}
