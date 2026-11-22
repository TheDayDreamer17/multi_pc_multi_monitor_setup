/*
 * mac_ddc.c - Native Apple Silicon DDC/CI Tool for OmniDisplay
 * Communicates directly with external displays via IOAVService (DCPAVServiceProxy).
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>

typedef CFTypeRef IOAVServiceRef;
extern IOAVServiceRef IOAVServiceCreateWithService(CFAllocatorRef allocator, io_service_t service);
extern IOReturn IOAVServiceWriteI2C(IOAVServiceRef service, uint32_t chipAddress, uint32_t dataAddress, void *inputBuffer, uint32_t inputBufferSize);
extern IOReturn IOAVServiceReadI2C(IOAVServiceRef service, uint32_t chipAddress, uint32_t offset, void *outputBuffer, uint32_t outputBufferSize);
extern IOReturn IOAVServiceCopyEDID(IOAVServiceRef service, CFDataRef *edidData);

#define MAX_DISPLAYS 16

static IOAVServiceRef g_services[MAX_DISPLAYS];
static char g_display_names[MAX_DISPLAYS][64];
static int g_service_count = 0;

static void extract_edid_name(const uint8_t *edid, size_t len, char *name_out) {
    strcpy(name_out, "External Display");
    if (len < 128) return;
    for (int block = 54; block <= 108; block += 18) {
        if (edid[block] == 0x00 && edid[block+1] == 0x00 && edid[block+2] == 0x00 && edid[block+3] == 0xFC) {
            int idx = 0;
            for (int i = 5; i < 18; i++) {
                char c = (char)edid[block + i];
                if (c == 0x0A || c == 0x00) break;
                name_out[idx++] = c;
            }
            name_out[idx] = '\0';
            return;
        }
    }
}

static void discover_displays(void) {
    g_service_count = 0;
    CFMutableDictionaryRef matching = IOServiceMatching("DCPAVServiceProxy");
    if (!matching) return;

    io_iterator_t iter;
    kern_return_t kr = IOServiceGetMatchingServices(kIOMainPortDefault, matching, &iter);
    if (kr != KERN_SUCCESS) return;

    io_service_t serv;
    while ((serv = IOIteratorNext(iter)) != 0 && g_service_count < MAX_DISPLAYS) {
        IOAVServiceRef av = IOAVServiceCreateWithService(kCFAllocatorDefault, serv);
        if (av) {
            g_services[g_service_count] = av;
            
            // Extract EDID monitor name
            CFDataRef edid = NULL;
            char name[64] = "External Display";
            if (IOAVServiceCopyEDID(av, &edid) == kIOReturnSuccess && edid) {
                extract_edid_name(CFDataGetBytePtr(edid), CFDataGetLength(edid), name);
                CFRelease(edid);
            }
            strncpy(g_display_names[g_service_count], name, 63);
            g_service_count++;
        }
        IOObjectRelease(serv);
    }
    IOObjectRelease(iter);
}

static bool set_vcp(IOAVServiceRef service, uint8_t vcp, uint16_t value) {
    if (!service) return false;

    // DDC/CI Set VCP command (6 bytes payload, dataAddress = 0x51)
    // [Length 0x84] [Command 0x03] [VCP] [Val_Hi] [Val_Lo] [Checksum]
    uint8_t packet[6];
    packet[0] = 0x84;
    packet[1] = 0x03;
    packet[2] = vcp;
    packet[3] = (uint8_t)((value >> 8) & 0xFF);
    packet[4] = (uint8_t)(value & 0xFF);

    // DDC/CI XOR checksum starting with 0x6E and 0x51
    uint8_t chk = 0x6E ^ 0x51 ^ packet[0] ^ packet[1] ^ packet[2] ^ packet[3] ^ packet[4];
    packet[5] = chk;

    // Standard I2C slave address 0x37, write offset 0x51
    IOReturn ret = IOAVServiceWriteI2C(service, 0x37, 0x51, packet, sizeof(packet));
    return (ret == kIOReturnSuccess);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <list | set <index> <vcp> <value>>\n", argv[0]);
        return 1;
    }

    discover_displays();

    if (strcmp(argv[1], "list") == 0) {
        printf("{\"count\": %d, \"displays\": [", g_service_count);
        for (int i = 0; i < g_service_count; i++) {
            printf("{\"index\": %d, \"name\": \"%s\"}%s", i, g_display_names[i], (i + 1 < g_service_count) ? ", " : "");
        }
        printf("]}\n");
        return 0;
    }

    if (strcmp(argv[1], "set") == 0) {
        if (argc < 5) {
            fprintf(stderr, "Usage: %s set <index> <vcp> <value>\n", argv[0]);
            return 1;
        }
        int idx = atoi(argv[2]);
        uint8_t vcp = (uint8_t)strtoul(argv[3], NULL, 0);
        uint16_t val = (uint16_t)strtoul(argv[4], NULL, 0);

        if (idx < 0 || idx >= g_service_count) {
            fprintf(stderr, "Error: Display index %d out of range (total %d)\n", idx, g_service_count);
            return 2;
        }

        bool ok = set_vcp(g_services[idx], vcp, val);
        if (ok) {
            printf("{\"status\": \"ok\", \"display\": %d, \"name\": \"%s\", \"vcp\": %u, \"value\": %u}\n", idx, g_display_names[idx], vcp, val);
            return 0;
        } else {
            fprintf(stderr, "{\"status\": \"error\", \"message\": \"IOAVServiceWriteI2C failed\"}\n");
            return 3;
        }
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    return 1;
}
