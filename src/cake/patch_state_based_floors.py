#!/usr/bin/env python3
"""
Patch autorate_continuous.py to support state-based floors
"""

import re
import sys

def patch_config_class(content: str) -> str:
    """Update Config class to load three floor values"""

    # Replace download floor loading
    old_dl_floor = r'        # Download parameters\n        dl = cm\[\'download\'\]\n        self\.download_floor = dl\[\'floor_mbps\'\] \* 1_000_000'
    new_dl_floor = '''        # Download parameters (STATE-BASED FLOORS)
        dl = cm['download']
        # Support both legacy (single floor) and v2 (state-based floors)
        if 'floor_green_mbps' in dl:
            self.download_floor_green = dl['floor_green_mbps'] * 1_000_000
            self.download_floor_yellow = dl['floor_yellow_mbps'] * 1_000_000
            self.download_floor_red = dl['floor_red_mbps'] * 1_000_000
        else:
            # Legacy: use single floor for all states
            floor = dl['floor_mbps'] * 1_000_000
            self.download_floor_green = floor
            self.download_floor_yellow = floor
            self.download_floor_red = floor'''

    content = re.sub(old_dl_floor, new_dl_floor, content)

    # Replace upload floor loading
    old_ul_floor = r'        # Upload parameters\n        ul = cm\[\'upload\'\]\n        self\.upload_floor = ul\[\'floor_mbps\'\] \* 1_000_000'
    new_ul_floor = '''        # Upload parameters (STATE-BASED FLOORS)
        ul = cm['upload']
        # Support both legacy (single floor) and v2 (state-based floors)
        if 'floor_green_mbps' in ul:
            self.upload_floor_green = ul['floor_green_mbps'] * 1_000_000
            self.upload_floor_yellow = ul['floor_yellow_mbps'] * 1_000_000
            self.upload_floor_red = ul['floor_red_mbps'] * 1_000_000
        else:
            # Legacy: use single floor for all states
            floor = ul['floor_mbps'] * 1_000_000
            self.upload_floor_green = floor
            self.upload_floor_yellow = floor
            self.upload_floor_red = floor'''

    content = re.sub(old_ul_floor, new_ul_floor, content)

    return content


def patch_queue_controller(content: str) -> str:
    """Update QueueController to use state-based floors"""

    # Update __init__ signature and attributes
    old_init = r'    def __init__\(self, name: str, floor: int, ceiling: int, step_up: int, factor_down: float\):\n        self\.name = name\n        self\.floor_bps = floor'

    new_init = '''    def __init__(self, name: str, floor_green: int, floor_yellow: int, floor_red: int, ceiling: int, step_up: int, factor_down: float):
        self.name = name
        self.floor_green_bps = floor_green
        self.floor_yellow_bps = floor_yellow
        self.floor_red_bps = floor_red'''

    content = re.sub(old_init, new_init, content, flags=re.MULTILINE)

    # Update adjust() method to use state-based floors
    old_adjust_floor = r'            new_rate = max\(new_rate, self\.floor_bps\)'
    new_adjust_floor = '''            # Use state-appropriate floor
            if zone == "RED":
                floor_bps = self.floor_red_bps
            elif zone == "YELLOW":
                floor_bps = self.floor_yellow_bps
            else:  # GREEN
                floor_bps = self.floor_green_bps
            new_rate = max(new_rate, floor_bps)'''

    content = re.sub(old_adjust_floor, new_adjust_floor, content)

    return content


def patch_controller_instantiation(content: str) -> str:
    """Update QueueController instantiation to pass three floors"""

    # Update download controller
    old_dl_inst = r'            floor=config\.download_floor,'
    new_dl_inst = '''            floor_green=config.download_floor_green,
            floor_yellow=config.download_floor_yellow,
            floor_red=config.download_floor_red,'''

    content = re.sub(old_dl_inst, new_dl_inst, content)

    # Update upload controller
    old_ul_inst = r'            floor=config\.upload_floor,'
    new_ul_inst = '''            floor_green=config.upload_floor_green,
            floor_yellow=config.upload_floor_yellow,
            floor_red=config.upload_floor_red,'''

    content = re.sub(old_ul_inst, new_ul_inst, content)

    return content


def patch_logging(content: str) -> str:
    """Update logging to show state-based floors"""

    # Update floor logging in startup message
    old_log = r'            logger\.info\(f"Download: \{config\.download_floor/1e6:.0f\}-\{config\.download_ceiling/1e6:.0f\}M'
    new_log = '''            logger.info(f"Download: GREEN={config.download_floor_green/1e6:.0f}M, YELLOW={config.download_floor_yellow/1e6:.0f}M, RED={config.download_floor_red/1e6:.0f}M, ceiling={config.download_ceiling/1e6:.0f}M'''

    content = re.sub(old_log, new_log, content)

    old_log2 = r'            logger\.info\(f"Upload: \{config\.upload_floor/1e6:.0f\}-\{config\.upload_ceiling/1e6:.0f\}M'
    new_log2 = '''            logger.info(f"Upload: GREEN={config.upload_floor_green/1e6:.0f}M, YELLOW={config.upload_floor_yellow/1e6:.0f}M, RED={config.upload_floor_red/1e6:.0f}M, ceiling={config.upload_ceiling/1e6:.0f}M'''

    content = re.sub(old_log2, new_log2, content)

    return content


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 patch_state_based_floors.py <input_file> <output_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Reading {input_file}...")
    with open(input_file, 'r') as f:
        content = f.read()

    print("Patching Config class...")
    content = patch_config_class(content)

    print("Patching QueueController class...")
    content = patch_queue_controller(content)

    print("Patching controller instantiation...")
    content = patch_controller_instantiation(content)

    print("Patching logging...")
    content = patch_logging(content)

    print(f"Writing {output_file}...")
    with open(output_file, 'w') as f:
        f.write(content)

    print("✅ Patching complete!")
    print("\nNext steps:")
    print("1. Review the patched file")
    print("2. Test with v2 config files")
    print("3. Deploy to containers")


if __name__ == "__main__":
    main()
