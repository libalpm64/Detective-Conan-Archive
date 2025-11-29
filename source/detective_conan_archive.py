#!/usr/bin/env python3
"""
Detective Conan Archival Project
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import json
import logging
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('detective_conan_processing.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(r"C:\Users\snoop\Desktop\Detective Conan (Fixing)")
CONFIG_FILE = BASE_DIR / "config.yaml"
SHOWS_DIR = BASE_DIR / "Shows"
FAN_SUBS_DIR = BASE_DIR / "fan subs 0001-0757"
BB_SUBS_DIR = BASE_DIR / "[Fabre-RAW] Detective Conan Remastered [NetflixJP] [1080p]"
TEMP_DIR = BASE_DIR / "temp_processing"

# tmp directory
TEMP_DIR.mkdir(exist_ok=True)

# Load configuration
def load_config() -> Dict:
    """Load configuration from YAML file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {CONFIG_FILE}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config file: {e}")
        logger.info("Using default configuration")
        return {
            'skip_dubbed_episodes': False,
            'dubbed_episodes': [],
            'subtitle_labels': {
                'fan_subs': 'Fan Subs [English]',
                'bb_subs': 'BB Subs [English]'
            }
        }

CONFIG = load_config()

# FFmpeg and FFSubSync paths (Change this!)
FFMPEG_PATH = r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = r"C:\Program Files\ffmpeg\bin\ffprobe.exe"

# Check if local ffmpeg exists
if not os.path.exists(FFMPEG_PATH):
    local_ffmpeg = BASE_DIR / "ffmpeg.exe"
    if local_ffmpeg.exists():
        FFMPEG_PATH = str(local_ffmpeg)
        FFPROBE_PATH = str(BASE_DIR / "ffprobe.exe")
    else:
        FFMPEG_PATH = "ffmpeg"
        FFPROBE_PATH = "ffprobe"


def extract_episode_number(filename: str) -> Optional[int]:
    """Extract episode number from filename."""
    patterns = [
        (r'\[RAW Reghost-Fabre\] Detective Conan (\d{1,4})', 1),  # Reghost-Fabre (Old Format)
        (r'\[Crunchyroll\] Detective Conan - (\d{1,4}) \[Multi-Sub\]', 1),
        (r'\[Fabre-RAW\] Detective Conan Remastered (\d{4})', 1),
        (r'\[Fabre-RAW\] Detective Conan (\d{4})', 1),
        (r'\[Erai-raws\] Detective Conan - (\d{4})', 1),
        (r'Detective Conan (\d{4})', 1),
    ]
    
    for pattern, group in patterns:
        match = re.search(pattern, filename)
        if match:
            return int(match.group(group))
    return None


def get_subtitle_path(ep_num: int, sub_type: str) -> Optional[Path]:
    """Get the path to the subtitle file for a given episode."""
    if sub_type == "fan":
        if 1 <= ep_num <= 757:
            sub_path = FAN_SUBS_DIR / f"{ep_num:04d}.ass"
            if sub_path.exists():
                return sub_path
    
    elif sub_type == "bb":
        if 124 <= ep_num <= 173:
            sub_path = BB_SUBS_DIR / f"[Fabre-RAW] Detective Conan Remastered {ep_num:04d} [NetflixJP] [1080p].srt"
        elif 174 <= ep_num <= 723:
            sub_path = BB_SUBS_DIR / f"[Fabre-RAW] Detective Conan {ep_num:04d} [NetflixJP] [1080p].srt"
        else:
            return None
        
        if sub_path.exists():
            return sub_path
    
    return None


def sync_subtitle(video_path: Path, subtitle_path: Path, output_path: Path) -> bool:
    """Synchronize subtitle to video using ffsubsync."""
    try:
        logger.info(f"Syncing subtitle: {subtitle_path.name}")
        
        cmd = [
            "ffs",
            str(video_path),
            "-i", str(subtitle_path),
            "-o", str(output_path)
        ]
        
        timeout = CONFIG.get('ffsubsync_timeout', 600)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully synced: {output_path.name}")
            return True
        else:
            logger.warning(f"FFSubSync failed, using original: {result.stderr[:200]}")
            shutil.copy2(subtitle_path, output_path)
            return False
    
    except subprocess.TimeoutExpired:
        logger.warning(f"FFSubSync timeout, using original subtitle")
        shutil.copy2(subtitle_path, output_path)
        return False
    except Exception as e:
        logger.error(f"Error syncing subtitle: {e}")
        shutil.copy2(subtitle_path, output_path)
        return False


def get_episode_config(ep_num: int) -> Dict:
    """Get configuration for a specific episode range."""
    if 1 <= ep_num <= 123:
        return CONFIG.get('episodes_1_123', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': False
        })
    elif 124 <= ep_num <= 723:
        return CONFIG.get('episodes_124_723', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': True
        })
    elif 724 <= ep_num <= 753:
        return CONFIG.get('episodes_724_753', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': False,
            'rename_existing_bb_track': True
        })
    else:  # 754-1132
        return CONFIG.get('episodes_754_1132', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': False
        })


def mux_subtitles_advanced(video_path: Path, fan_sub_path: Optional[Path], 
                           bb_sub_path: Optional[Path], output_path: Path,
                           ep_config: Dict) -> bool:
    """Mux subtitles and handle existing tracks."""
    try:
        ep_num = extract_episode_number(video_path.name)
        logger.info(f"Muxing subtitles for episode {ep_num}")
        
        # Build ffmpeg command
        cmd = [FFMPEG_PATH, "-i", str(video_path)]
        
        input_count = 1
        subtitle_maps = []
        metadata = []
        
        # Map video and audio from original
        cmd.extend(["-map", "0:v", "-map", "0:a"])
        
        # Handle existing subtitle tracks
        if ep_config.get('keep_existing_subs', True):
            # For episodes 724-753, we need to rename existing BB track
            if ep_config.get('rename_existing_bb_track', False):
                # Map existing subtitle tracks
                cmd.extend(["-map", "0:s?"])
                # Metadata to rename the first subtitle track
                bb_label = CONFIG.get('subtitle_labels', {}).get('bb_subs', 'BB Subs [English]')
                metadata.extend([
                    "-metadata:s:s:0", "language=eng",
                    "-metadata:s:s:0", f"title={bb_label}"
                ])
            else:
                # Just keep all existing subtitles
                cmd.extend(["-map", "0:s?"])
        
        # Add new subtitle files
        subtitle_index = 1 if ep_config.get('rename_existing_bb_track', False) else 0
        
        if fan_sub_path and fan_sub_path.exists() and ep_config.get('add_fan_subs', True):
            cmd.extend(["-i", str(fan_sub_path)])
            subtitle_maps.append(f"-map {input_count}:s")
            fan_label = CONFIG.get('subtitle_labels', {}).get('fan_subs', 'Fan Subs [English]')
            metadata.extend([
                f"-metadata:s:s:{subtitle_index}", "language=eng",
                f"-metadata:s:s:{subtitle_index}", f"title={fan_label}"
            ])
            input_count += 1
            subtitle_index += 1
        
        if bb_sub_path and bb_sub_path.exists() and ep_config.get('add_bb_subs', True):
            cmd.extend(["-i", str(bb_sub_path)])
            subtitle_maps.append(f"-map {input_count}:s")
            bb_label = CONFIG.get('subtitle_labels', {}).get('bb_subs', 'BB Subs [English]')
            metadata.extend([
                f"-metadata:s:s:{subtitle_index}", "language=eng",
                f"-metadata:s:s:{subtitle_index}", f"title={bb_label}"
            ])
            input_count += 1
        
        # Add new subtitle maps
        for sub_map in subtitle_maps:
            cmd.extend(sub_map.split())
        
        # Add metadata
        cmd.extend(metadata)
        
        # Copy codecs
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "copy"
        ])
        
        # Output file
        cmd.append(str(output_path))
        
        # Run ffmpeg
        timeout = CONFIG.get('ffmpeg_timeout', 300)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully muxed: {output_path.name}")
            return True
        else:
            logger.error(f"FFmpeg muxing failed: {result.stderr[:500]}")
            return False
    
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg timeout for {video_path.name}")
        return False
    except Exception as e:
        logger.error(f"Error muxing subtitles: {e}")
        return False


def process_episode(video_path: Path, ep_num: int) -> bool:
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Episode {ep_num}: {video_path.name}")
        logger.info(f"{'='*60}")
        
        # Check if this is the "Old Format" (Reghost-Fabre)
        is_old_format = "[RAW Reghost-Fabre]" in video_path.name
        if is_old_format:
            logger.info("Detected Old Format (Reghost-Fabre)")
        
        # Check if we should skip dubbed episodes
        skip_dubbed = CONFIG.get('skip_dubbed_episodes', False)
        dubbed_episodes = set(CONFIG.get('dubbed_episodes', []))
        
        if skip_dubbed and ep_num in dubbed_episodes:
            logger.info(f"Episode {ep_num} is dubbed (CR-USA), skipping per config")
            # Just rename
            if is_old_format:
                new_name = f"Detective Conan {ep_num:04d} [480p].mkv"
            else:
                new_name = f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"
                
            new_path = video_path.parent / new_name
            if video_path.name != new_name:
                logger.info(f"Renaming: {video_path.name} -> {new_name}")
                video_path.rename(new_path)
            return True
        
        # Get episode-specific configuration
        ep_config = get_episode_config(ep_num)
        
        # Get subtitle paths
        fan_sub_original = None
        bb_sub_original = None
        
        if ep_config.get('add_fan_subs', True):
            fan_sub_original = get_subtitle_path(ep_num, "fan")
        
        if ep_config.get('add_bb_subs', True):
            bb_sub_original = get_subtitle_path(ep_num, "bb")
        
        # Check if we have any subtitles to add
        if not fan_sub_original and not bb_sub_original:
            if ep_config.get('keep_existing_subs', True):
                logger.info(f"No new subtitles to add for episode {ep_num}, keeping existing")
                # Just rename
                if is_old_format:
                    new_name = f"Detective Conan {ep_num:04d} [480p].mkv"
                else:
                    new_name = f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"
                    
                new_path = video_path.parent / new_name
                if video_path.name != new_name:
                    logger.info(f"Renaming: {video_path.name} -> {new_name}")
                    video_path.rename(new_path)
                return True
            else:
                logger.warning(f"No subtitles found for episode {ep_num}")
                return False
        
        # Sync subtitles
        fan_sub_synced = None
        bb_sub_synced = None
        
        if fan_sub_original:
            fan_sub_synced = TEMP_DIR / f"{ep_num:04d}_fan_synced.ass"
            sync_subtitle(video_path, fan_sub_original, fan_sub_synced)
        
        if bb_sub_original:
            bb_sub_synced = TEMP_DIR / f"{ep_num:04d}_bb_synced.srt"
            sync_subtitle(video_path, bb_sub_original, bb_sub_synced)
        
        # Create output paths
        if is_old_format:
            output_name = f"Detective Conan {ep_num:04d} [480p].mkv"
        else:
            output_name = f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"
            
        output_path = video_path.parent / output_name
        temp_output = TEMP_DIR / f"temp_{ep_num:04d}.mkv"
        
        # Mux subtitles
        success = mux_subtitles_advanced(
            video_path,
            fan_sub_synced,
            bb_sub_synced,
            temp_output,
            ep_config
        )
        
        if success and temp_output.exists():
            # Remove original if different name
            if video_path != output_path and video_path.exists():
                video_path.unlink()
            
            # Move file to final location
            shutil.move(str(temp_output), str(output_path))
            logger.info(f"[OK] Episode {ep_num} processed successfully")
            
            # Clean up temp subtitle files
            if fan_sub_synced and fan_sub_synced.exists():
                fan_sub_synced.unlink()
            if bb_sub_synced and bb_sub_synced.exists():
                bb_sub_synced.unlink()
            
            return True
        
        logger.error(f"[FAIL] Failed to process episode {ep_num}")
        return False
    
    except Exception as e:
        logger.error(f"Error processing episode {ep_num}: {e}")
        return False


def process_season(season_dir: Path):
    """Process a season directory."""
    logger.info(f"\n{'#'*60}")
    logger.info(f"Processing Season: {season_dir.name}")
    logger.info(f"{'#'*60}\n")
    
    video_files = []
    for file in season_dir.glob("*.mkv"):
        ep_num = extract_episode_number(file.name)
        if ep_num:
            video_files.append((file, ep_num))
    
    video_files.sort(key=lambda x: x[1])
    
    if not video_files:
        logger.warning(f"No video files found in {season_dir.name}")
        return
    
    logger.info(f"Found {len(video_files)} episodes in {season_dir.name}")
    
    for video_path, ep_num in video_files:
        process_episode(video_path, ep_num)


def main():
    """Main processing function."""
    logger.info("="*60)
    logger.info("Detective Conan Archival Project - Subtitle Processing V2")
    logger.info("="*60)
    
    # Show configuration
    # logger.info(f"\nConfiguration:")
    # logger.info(f"  Skip dubbed episodes: {CONFIG.get('skip_dubbed_episodes', False)}")
    # logger.info(f"  Fan subs label: {CONFIG.get('subtitle_labels', {}).get('fan_subs', 'Fan Subs [English]')}")
    # logger.info(f"  BB subs label: {CONFIG.get('subtitle_labels', {}).get('bb_subs', 'BB Subs [English]')}")
    
    # Check for FFmpeg & FFSubSync
    try:
        result = subprocess.run(["ffs", "--version"], capture_output=True, text=True)
        logger.info(f"\nFFSubSync: {result.stdout.strip()}")
    except FileNotFoundError:
        logger.error("FFSubSync not found! Install with: pip install ffsubsync")
        return
    
    try:
        result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True)
        logger.info(f"FFmpeg: {FFMPEG_PATH}")
    except FileNotFoundError:
        logger.error(f"FFmpeg not found at {FFMPEG_PATH}")
        return
    
    # Grab season directories
    season_dirs = sorted([d for d in SHOWS_DIR.iterdir() if d.is_dir() and "Season" in d.name])
    logger.info(f"\nFound {len(season_dirs)} season directories\n")
    
    # Iterate through each season
    for season_dir in season_dirs:
        process_season(season_dir)
    
    logger.info("\n" + "="*60)
    logger.info("Processing Complete!")
    logger.info("="*60)


if __name__ == "__main__":
    try:
        import yaml
    except ImportError:
        logger.error("PyYAML not installed. Installing...")
        subprocess.run(["pip", "install", "pyyaml"], check=True)
        import yaml
    
    main()