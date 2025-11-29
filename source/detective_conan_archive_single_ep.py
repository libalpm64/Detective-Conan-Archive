#!/usr/bin/env python3
"""Detective Conan - Single Episode Test"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from detective_conan_archive import (
    process_episode,
    extract_episode,
    get_episode_config,
    detect_source,
    DIRS,
    CONFIG,
    logger
)


def test_episode(ep_num: int) -> bool:
    """Test processing a single episode."""
    logger.info(f"\n{'='*50}\nTesting Episode {ep_num}\n{'='*50}")
    
    # Find the episode file
    for season in sorted(DIRS['shows_dir'].iterdir()):
        if not season.is_dir() or "Season" not in season.name:
            continue
        
        for video in season.glob("*.mkv"):
            if extract_episode(video.name) == ep_num:
                logger.info(f"Found: {video.name}")
                logger.info(f"Location: {season.name}")
                
                # Show config
                source = detect_source(video.name)
                config = get_episode_config(ep_num, source)
                logger.info(f"Source: {source}")
                logger.info(f"Config: {config}")
                
                # Process
                success = process_episode(video, ep_num)
                logger.info(f"\n{'[OK]' if success else '[FAIL]'} Episode {ep_num}")
                return success
    
    logger.error(f"Episode {ep_num} not found")
    return False


def main():
    print("="*50)
    print("Detective Conan - Single Episode Test")
    print("="*50)
    print(f"\nSkip dubbed: {CONFIG.get('skip_dubbed_episodes', False)}")
    print("\nTest episodes:")
    print("  6   - Crunchyroll (keep existing)")
    print("  124 - First Fan + BB subs")
    print("  200 - Mid-range Fan + BB")
    print("  724 - Fabre/Netflix (Fan + BB from SRT)")
    print("  754 - Erai-raws (keep CR, add fan)")
    
    while True:
        try:
            inp = input("\nEpisode number (q to quit): ").strip()
            if inp.lower() == 'q':
                return
            
            ep = int(inp)
            if not 1 <= ep <= 1132:
                print("Must be 1-1132")
                continue
            break
        except ValueError:
            print("Enter a valid number")
    
    print(f"\nProcessing episode {ep}...\n")
    success = test_episode(ep)
    print(f"\n{'='*50}\n{'Success' if success else 'Failed'}\n{'='*50}")


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        import subprocess
        subprocess.run(["pip", "install", "pyyaml"], check=True)
    
    main()