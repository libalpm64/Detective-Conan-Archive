#!/usr/bin/env python3
"""
Detective Conan - Single Episode Test
Catch issues early with a single episode
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detective_conan_archive import (
    process_episode,
    extract_episode_number,
    SHOWS_DIR,
    CONFIG,
    logger
)
from pathlib import Path


def test_single_episode(episode_number: int):
    logger.info(f"\n{'='*60}")
    logger.info(f"Testing ep: {episode_number}")
    logger.info(f"{'='*60}\n")
    
    from process_detective_conan_v2 import get_episode_config
    ep_config = get_episode_config(episode_number)
    logger.info(f"Episode {episode_number} configuration:")
    for key, value in ep_config.items():
        logger.info(f"  {key}: {value}")
    logger.info("")
    
    found = False
    for season_dir in sorted(SHOWS_DIR.iterdir()):
        if not season_dir.is_dir() or "Season" not in season_dir.name:
            continue
        
        for video_file in season_dir.glob("*.mkv"):
            ep_num = extract_episode_number(video_file.name)
            if ep_num == episode_number:
                logger.info(f"Found episode {episode_number}: {video_file.name}")
                logger.info(f"Location: {video_file.parent.name}\n")
                
                success = process_episode(video_file, ep_num)
                
                if success:
                    logger.info(f"\n[OK] Successfully processed episode {episode_number}")
                else:
                    logger.error(f"\n[FAIL] Failed to process episode {episode_number}")
                
                found = True
                break
        
        if found:
            break
    
    if not found:
        logger.error(f"Could not find episode {episode_number}")
        return False
    
    return True


def main():
    print("="*60)
    print("Detective Conan - Single Episode Test")
    print("="*60)
    print()
    print("Current configuration:")
    print(f"  Skip dubbed episodes: {CONFIG.get('skip_dubbed_episodes', False)}")
    print()
    print("Recommended test episodes:")
    print("  - Episode 6:   Crunchyroll Multi-Sub (keeps existing subs)")
    print("  - Episode 124: First episode with both Fan + BB subs")
    print("  - Episode 200: Middle episode with both subs")
    print("  - Episode 724: BB subs embedded (rename track)")
    print("  - Episode 754: Erai-raws (keep CR subs, add fan)")
    print()
    
    while True:
        try:
            ep_input = input("Enter episode number to test (or 'q' to quit): ").strip()
            
            if ep_input.lower() == 'q':
                print("Exiting...")
                return
            
            episode_number = int(ep_input)
            
            if episode_number < 1 or episode_number > 1132:
                print("Episode number must be between 1 and 1132")
                continue
            
            break
        except ValueError:
            print("Please enter a valid number")
    
    print()
    print(f"Processing episode {episode_number}...")
    print()
    
    success = test_single_episode(episode_number)
    
    if success:
        print()
        print("="*60)
        print("Sucess.")
        print("="*60)
        print()
    else:
        print()
        print("="*60)
        print("Failed.")
        print("="*60)


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        print("Installing PyYAML...")
        import subprocess
        subprocess.run(["pip", "install", "pyyaml"], check=True)
    
    main()