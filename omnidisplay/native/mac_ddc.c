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

#define MAX_DISPLAYS 16

static IOAVServiceRef g_services[MAX_DISPLAYS];
static int g_service_count = 0;

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
            g_services[g_service_count++] = av;
        }
        IOObjectRelease(serv);
    }
    IOObjectRelease(iter);
}

static bool set_vcp(IOAVServiceRef service, uint8_t vcp, uint16_t value) {
    if (!service) return false;

    // DDC/CI Set VCP command
    // [Source 0x51] [Length 0x84] [Command 0x03] [VCP] [Val_Hi] [Val_Lo] [Checksum]
    uint8_t packet[7];
    packet[0] = 0x51;
    packet[1] = 0x84;
    packet[2] = 0x03;
    packet[3] = vcp;
    packet[4] = (uint8_t)((value >> 8) & 0xFF);
    packet[5] = (uint8_t)(value & 0xFF);

    // DDC/CI XOR checksum starting with 0x6E (7-bit address 0x37 shifted left)
    uint8_t chk = 0x6E ^ packet[0] ^ packet[1] ^ packet[2] ^ packet[3] ^ packet[4] ^ packet[5];
    packet[6] = chk;

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
        printf("{\"count\": %d}\n", g_service_count);
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
            printf("{\"status\": \"ok\", \"display\": %d, \"vcp\": %u, \"value\": %u}\n", idx, vcp, val);
            return 0;
        } else {
            fprintf(stderr, "{\"status\": \"error\", \"message\": \"IOAVServiceWriteI2C failed\"}\n");
            return 3;
        }
    }

    fprintf(stderr, "Unknown command: %s\n", argv[1]);
    return 1;
}
