/*
 * mac_layout.c - Display layout helper for OmniDisplay (macOS)
 *
 * Usage:
 *   mac_layout list                     -> JSON list of online external displays
 *   mac_layout mirror <ghostID> <mainID> -> mirror ghost display onto main (removes it from desktop space)
 *   mac_layout unmirror-all             -> stop mirroring on every display
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <CoreGraphics/CoreGraphics.h>

#define MAX_D 16

static int do_list(void) {
    CGDirectDisplayID ids[MAX_D];
    uint32_t n = 0;
    CGGetOnlineDisplayList(MAX_D, ids, &n);
    printf("{\"displays\": [");
    int first = 1;
    for (uint32_t i = 0; i < n; i++) {
        if (CGDisplayIsBuiltin(ids[i])) continue;
        CGRect b = CGDisplayBounds(ids[i]);
        printf("%s{\"id\": %u, \"x\": %d, \"y\": %d, \"w\": %d, \"h\": %d, \"mirrored\": %s}",
               first ? "" : ", ", ids[i], (int)b.origin.x, (int)b.origin.y,
               (int)b.size.width, (int)b.size.height,
               CGDisplayIsInMirrorSet(ids[i]) ? "true" : "false");
        first = 0;
    }
    printf("]}\n");
    return 0;
}

static int do_config(CGDirectDisplayID target, CGDirectDisplayID mirror_of, int all) {
    CGDisplayConfigRef cfg;
    if (CGBeginDisplayConfiguration(&cfg) != kCGErrorSuccess) return 2;
    if (all) {
        CGDirectDisplayID ids[MAX_D];
        uint32_t n = 0;
        CGGetOnlineDisplayList(MAX_D, ids, &n);
        for (uint32_t i = 0; i < n; i++) {
            if (CGDisplayMirrorsDisplay(ids[i]) != kCGNullDirectDisplay)
                CGConfigureDisplayMirrorOfDisplay(cfg, ids[i], kCGNullDirectDisplay);
        }
    } else {
        CGConfigureDisplayMirrorOfDisplay(cfg, target, mirror_of);
    }
    if (CGCompleteDisplayConfiguration(cfg, kCGConfigureForSession) != kCGErrorSuccess) {
        CGCancelDisplayConfiguration(cfg);
        return 3;
    }
    return 0;
}

int main(int argc, char *argv[]) {
    if (argc >= 2 && strcmp(argv[1], "list") == 0) return do_list();
    if (argc >= 2 && strcmp(argv[1], "unmirror-all") == 0) return do_config(0, 0, 1);
    if (argc >= 4 && strcmp(argv[1], "mirror") == 0)
        return do_config((CGDirectDisplayID)strtoul(argv[2], NULL, 10),
                         (CGDirectDisplayID)strtoul(argv[3], NULL, 10), 0);
    fprintf(stderr, "Usage: %s <list | mirror <ghostID> <mainID> | unmirror-all>\n", argv[0]);
    return 1;
}
