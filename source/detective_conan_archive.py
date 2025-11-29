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

# logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    logger.error("PyYAML not installed. Installing...")
    subprocess.run(["pip", "install", "pyyaml"], check=True)
    import yaml


def get_default_config() -> Dict:
    """Return default configuration."""
    return {
        'skip_dubbed_episodes': False,
        'dubbed_episodes': [],
        'subtitle_labels': {
            'fan_subs': 'Fan Subs [English]',
            'bb_subs': 'BB Subs [English]'
        },
        'directories': {
            'base_dir': str(Path(__file__).parent),
            'shows_dir': 'Shows',
            'fan_subs_dir': 'fan subs 0001-0757',
            'bb_subs_dir': '[Fabre-RAW] Detective Conan Remastered [NetflixJP] [1080p]',
            'temp_dir': 'temp_processing',
            'ffmpeg_dir': None
        },
        'ffsubsync_timeout': 45,
        'ffmpeg_timeout': 300,
        'create_backups': False,
        'cleanup_temp_files': True,
        'log_level': 'INFO',
        'log_file': 'detective_conan_processing.log'
    }


def find_config_file() -> Optional[Path]:
    """Find the config file in common locations."""
    # Check current directory first
    locations = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
        Path(__file__).parent / "config.yaml",
        Path(__file__).parent / "config.yml",
    ]
    
    for loc in locations:
        if loc.exists():
            return loc
    
    return None


def load_config() -> Dict:
    """Load configuration from YAML file."""
    config_file = find_config_file()
    
    if config_file:
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_file}")
            
            # Merge with defaults
            default_config = get_default_config()
            
            # Deep merge for nested dicts
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
                elif isinstance(value, dict) and isinstance(config.get(key), dict):
                    for sub_key, sub_value in value.items():
                        if sub_key not in config[key]:
                            config[key][sub_key] = sub_value
            
            return config
        except Exception as e:
            logger.error(f"Failed to load config file: {e}")
            logger.info("Using default configuration")
            return get_default_config()
    else:
        logger.warning("No config file found, using default configuration")
        return get_default_config()


def setup_directories(config: Dict) -> Dict[str, Path]:
    """Setup directory paths from configuration."""
    dirs_config = config.get('directories', {})
    
    # Get basedir
    base_dir_str = dirs_config.get('base_dir', str(Path.cwd()))
    base_dir = Path(base_dir_str)
    
    # Relative to basedir
    def resolve_path(path_str: str, default: str) -> Path:
        if not path_str:
            path_str = default
        path = Path(path_str)
        if not path.is_absolute():
            path = base_dir / path
        return path
    
    directories = {
        'base_dir': base_dir,
        'shows_dir': resolve_path(dirs_config.get('shows_dir'), 'Shows'),
        'fan_subs_dir': resolve_path(dirs_config.get('fan_subs_dir'), 'fan subs 0001-0757'),
        'bb_subs_dir': resolve_path(dirs_config.get('bb_subs_dir'), '[Fabre-RAW] Detective Conan Remastered [NetflixJP] [1080p]'),
        'temp_dir': resolve_path(dirs_config.get('temp_dir'), 'temp_processing'),
    }
    
    # Handle ffmpeg_dir
    ffmpeg_dir = dirs_config.get('ffmpeg_dir')
    if ffmpeg_dir:
        directories['ffmpeg_dir'] = Path(ffmpeg_dir)
    else:
        directories['ffmpeg_dir'] = None
    
    return directories


def setup_logging(config: Dict, log_dir: Path):
    """Setup logging based on configuration."""
    log_level_str = config.get('log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    log_file = config.get('log_file', 'detective_conan_processing.log')
    log_path = log_dir / log_file
    
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(log_level)
    
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    logger.info(f"Logging configured: level={log_level_str}, file={log_path}")


def setup_ffmpeg(directories: Dict) -> Tuple[str, str]:
    """Setup FFmpeg paths."""
    ffmpeg_dir = directories.get('ffmpeg_dir')
    
    if ffmpeg_dir and ffmpeg_dir.exists():
        ffmpeg_path = str(ffmpeg_dir / "ffmpeg.exe")
        ffprobe_path = str(ffmpeg_dir / "ffprobe.exe")
        
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path, ffprobe_path
    
    # Check common locations
    common_paths = [
        r"C:\Program Files\ffmpeg\bin",
        r"C:\ffmpeg\bin",
        str(directories['base_dir']),
    ]
    
    for path in common_paths:
        ffmpeg_path = os.path.join(path, "ffmpeg.exe")
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path, os.path.join(path, "ffprobe.exe")
    
    # Fallback to system PATH
    return "ffmpeg", "ffprobe"


# Load configuration
CONFIG = load_config()

# Setup directories
DIRECTORIES = setup_directories(CONFIG)

# Setup logging
setup_logging(CONFIG, DIRECTORIES['base_dir'])

# Setup FFmpeg
FFMPEG_PATH, FFPROBE_PATH = setup_ffmpeg(DIRECTORIES)

# Create temp directory
DIRECTORIES['temp_dir'].mkdir(exist_ok=True)

# Log directory setup
logger.info("="*60)
logger.info("Directory Configuration:")
logger.info(f"  Base Dir:     {DIRECTORIES['base_dir']}")
logger.info(f"  Shows Dir:    {DIRECTORIES['shows_dir']}")
logger.info(f"  Fan Subs Dir: {DIRECTORIES['fan_subs_dir']}")
logger.info(f"  BB Subs Dir:  {DIRECTORIES['bb_subs_dir']}")
logger.info(f"  Temp Dir:     {DIRECTORIES['temp_dir']}")
logger.info(f"  FFmpeg:       {FFMPEG_PATH}")
logger.info("="*60)


def detect_source_format(filename: str) -> str:
    """Detect the source format of the video file."""
    if "[Erai-raws] Detective Conan -" in filename and "[Multiple Subtitle]" in filename:
        return "erai-raws"
    elif "[RAW Reghost-Fabre]" in filename:
        return "reghost-fabre"
    elif "[Crunchyroll]" in filename:
        return "crunchyroll"
    elif "[Fabre-RAW] Detective Conan Remastered" in filename:
        return "fabre-remastered"
    elif "[Fabre-RAW] Detective Conan" in filename:
        return "fabre"
    elif "Bilibili" in filename or "bilibili" in filename:  # <--- ADD THIS
        return "bilibili"
    else:
        return "unknown"

def extract_episode_number(filename: str) -> Optional[int]:
    """Extract episode number from filename."""
    patterns = [
        (r'\[Erai-raws\] Detective Conan - (\d{4}) \[1080p\]\[Multiple Subtitle\]', 1),  # Erai-raws NEW
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
            sub_path = DIRECTORIES['fan_subs_dir'] / f"{ep_num:04d}.ass"
            if sub_path.exists():
                return sub_path
    
    elif sub_type == "bb":
        if 124 <= ep_num <= 173:
            sub_path = DIRECTORIES['bb_subs_dir'] / f"[Fabre-RAW] Detective Conan Remastered {ep_num:04d} [NetflixJP] [1080p].srt"
        elif 174 <= ep_num <= 723:
            sub_path = DIRECTORIES['bb_subs_dir'] / f"[Fabre-RAW] Detective Conan {ep_num:04d} [NetflixJP] [1080p].srt"
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
        
        timeout = CONFIG.get('ffsubsync_timeout', 45)
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


def get_episode_config(ep_num: int, source_format: str) -> Dict:
    """Get configuration for a specific episode range and source format."""
    
    # Erai-raws episodes 1-123: Already have good subs, just rename
    if source_format == "erai-raws" and 1 <= ep_num <= 123:
        return {
            'rename_only': True,
            'output_format': 'remastered',
            'keep_existing_subs': True,
            'add_fan_subs': False,
            'add_bb_subs': False
        }
    
    # Standard processing for other formats/episodes
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
        # Default config for this range (Fabre/Netflix files)
        config = CONFIG.get('episodes_724_753', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': False,
            'rename_existing_bb_track': True
        })
        
        if source_format == 'bilibili':
            config['rename_existing_bb_track'] = False
            
        return config
    else:  # 754-1132
        return CONFIG.get('episodes_754_1132', {
            'keep_existing_subs': True,
            'add_fan_subs': True,
            'add_bb_subs': False
        })


def get_output_filename(ep_num: int, source_format: str, ep_config: Dict) -> str:
    """Generate the output filename based on episode and format."""
    
    # Check for explicit output format in config
    output_format = ep_config.get('output_format', None)
    
    if output_format == 'remastered':
        return f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"
    elif output_format == '480p':
        return f"Detective Conan {ep_num:04d} [480p].mkv"
    
    # Default logic based on source format
    if source_format == "reghost-fabre":
        return f"Detective Conan {ep_num:04d} [480p].mkv"
    elif source_format == "erai-raws":
        return f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"
    else:
        return f"Detective Conan Remastered {ep_num:04d} [1080p].mkv"

def mux_subtitles_advanced(video_path: Path, fan_sub_path: Optional[Path], 
                           bb_sub_path: Optional[Path], output_path: Path,
                           ep_config: Dict) -> bool:
    """Mux subtitles and handle existing tracks."""
    try:
        ep_num = extract_episode_number(video_path.name)
        logger.info(f"Muxing subtitles for episode {ep_num}")
        
        # 1. Start command with the main video input
        cmd = [FFMPEG_PATH, "-i", str(video_path)]
        
        # Lists to hold different parts of the command
        additional_inputs = []
        output_maps = []
        metadata = []
        
        # 2. Setup Maps for the Main Video (Input 0)
        output_maps.extend(["-map", "0:v", "-map", "0:a"])
        
        keep_existing = ep_config.get('keep_existing_subs', True)
        rename_existing = ep_config.get('rename_existing_bb_track', False)

        if keep_existing:
            output_maps.extend(["-map", "0:s?"])
            
            if rename_existing:
                bb_label = CONFIG.get('subtitle_labels', {}).get('bb_subs', 'BB Subs [English]')
                metadata.extend([
                    "-metadata:s:s:0", "language=eng",
                    "-metadata:s:s:0", f"title={bb_label}"
                ])
        
        # 3. logic for New Subtitles
        # We track input_count starting at 1 because video_path is input 0
        input_count = 1
        
        # Calculate metadata index for new streams
        # If keeping existing subs, assume at least 1 exists (index 0), so new ones start at 1
        # If NOT keeping existing, new ones start at 0
        subtitle_index = 1 if keep_existing else 0
        
        # Fan Subs
        if fan_sub_path and fan_sub_path.exists() and ep_config.get('add_fan_subs', True):
            additional_inputs.extend(["-i", str(fan_sub_path)])
            output_maps.extend(["-map", f"{input_count}:s"])
            
            fan_label = CONFIG.get('subtitle_labels', {}).get('fan_subs', 'Fan Subs [English]')
            metadata.extend([
                f"-metadata:s:s:{subtitle_index}", "language=eng",
                f"-metadata:s:s:{subtitle_index}", f"title={fan_label}"
            ])
            input_count += 1
            subtitle_index += 1
        
        # BB Subs
        if bb_sub_path and bb_sub_path.exists() and ep_config.get('add_bb_subs', True):
            additional_inputs.extend(["-i", str(bb_sub_path)])
            output_maps.extend(["-map", f"{input_count}:s"])
            
            bb_label = CONFIG.get('subtitle_labels', {}).get('bb_subs', 'BB Subs [English]')
            metadata.extend([
                f"-metadata:s:s:{subtitle_index}", "language=eng",
                f"-metadata:s:s:{subtitle_index}", f"title={bb_label}"
            ])
            input_count += 1
        
        # 4. Construct Final Command
        # Order: [ffmpeg] [input 0] [input 1..N] [maps] [metadata] [codecs] [output]
        cmd.extend(additional_inputs)
        cmd.extend(output_maps)
        cmd.extend(metadata)
        
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "copy",
            "-y"
        ])
        
        cmd.append(str(output_path))
        
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        timeout = CONFIG.get('ffmpeg_timeout', 300)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully muxed: {output_path.name}")
            return True
        else:
            logger.error(f"FFmpeg muxing failed for {video_path.name}")
            error_log = result.stderr[-2000:] if result.stderr else "No error output"
            logger.error(f"Error log:\n{error_log}")
            return False
    
    except subprocess.TimeoutExpired:
        logger.error(f"FFmpeg timeout for {video_path.name}")
        return False
    except Exception as e:
        logger.error(f"Error muxing subtitles: {e}")
        return False


def create_backup(video_path: Path) -> Optional[Path]:
    """Create a backup of the original file."""
    if not CONFIG.get('create_backups', False):
        return None
    
    backup_dir = DIRECTORIES['base_dir'] / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    backup_path = backup_dir / video_path.name
    
    try:
        shutil.copy2(video_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return None


def cleanup_temp_files():
    """Clean up temporary files."""
    if not CONFIG.get('cleanup_temp_files', True):
        return
    
    temp_dir = DIRECTORIES['temp_dir']
    
    try:
        for file in temp_dir.glob("*"):
            if file.is_file():
                file.unlink()
        logger.info("Cleaned up temporary files")
    except Exception as e:
        logger.error(f"Error cleaning up temp files: {e}")


def process_episode(video_path: Path, ep_num: int) -> bool:
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing Episode {ep_num}: {video_path.name}")
        logger.info(f"{'='*60}")
        
        # Create backup if configured
        create_backup(video_path)
        
        # Detect source format
        source_format = detect_source_format(video_path.name)
        logger.info(f"Detected source format: {source_format}")
        
        # Get episode-specific configuration
        ep_config = get_episode_config(ep_num, source_format)
        
        # Generate output filename
        output_name = get_output_filename(ep_num, source_format, ep_config)
        output_path = video_path.parent / output_name
        
        # Check if we should skip dubbed episodes
        skip_dubbed = CONFIG.get('skip_dubbed_episodes', False)
        dubbed_episodes = set(CONFIG.get('dubbed_episodes', []))
        
        if skip_dubbed and ep_num in dubbed_episodes:
            logger.info(f"Episode {ep_num} is dubbed (CR-USA), skipping per config")
            if video_path.name != output_name:
                logger.info(f"Renaming: {video_path.name} -> {output_name}")
                video_path.rename(output_path)
            return True
        
        # RENAME ONLY MODE (for Erai-raws 1-123)
        if ep_config.get('rename_only', False):
            logger.info(f"Rename-only mode for episode {ep_num}")
            if video_path.name != output_name:
                logger.info(f"Renaming: {video_path.name} -> {output_name}")
                video_path.rename(output_path)
                logger.info(f"[OK] Episode {ep_num} renamed successfully")
            else:
                logger.info(f"[OK] Episode {ep_num} already has correct name")
            return True
        
        # Get subtitle paths
        fan_sub_original = None
        bb_sub_original = None
        
        if ep_config.get('add_fan_subs', True):
            fan_sub_original = get_subtitle_path(ep_num, "fan")
            if fan_sub_original:
                logger.info(f"Found fan subs: {fan_sub_original.name}")
            else:
                logger.debug(f"No fan subs found for episode {ep_num}")
        
        if ep_config.get('add_bb_subs', True):
            bb_sub_original = get_subtitle_path(ep_num, "bb")
            if bb_sub_original:
                logger.info(f"Found BB subs: {bb_sub_original.name}")
            else:
                logger.debug(f"No BB subs found for episode {ep_num}")
        
        # Check if we have any subtitles to add
        if not fan_sub_original and not bb_sub_original:
            if ep_config.get('keep_existing_subs', True):
                logger.info(f"No new subtitles to add for episode {ep_num}, keeping existing")
                if video_path.name != output_name:
                    logger.info(f"Renaming: {video_path.name} -> {output_name}")
                    video_path.rename(output_path)
                return True
            else:
                logger.warning(f"No subtitles found for episode {ep_num}")
                return False
        
        # Sync subtitles
        fan_sub_synced = None
        bb_sub_synced = None
        
        if fan_sub_original:
            fan_sub_synced = DIRECTORIES['temp_dir'] / f"{ep_num:04d}_fan_synced.ass"
            sync_subtitle(video_path, fan_sub_original, fan_sub_synced)
        
        if bb_sub_original:
            bb_sub_synced = DIRECTORIES['temp_dir'] / f"{ep_num:04d}_bb_synced.srt"
            sync_subtitle(video_path, bb_sub_original, bb_sub_synced)
        
        # Create temp output path
        temp_output = DIRECTORIES['temp_dir'] / f"temp_{ep_num:04d}.mkv"
        
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
            elif video_path == output_path and video_path.exists():
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
        import traceback
        logger.debug(traceback.format_exc())
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
        else:
            logger.warning(f"Could not extract episode number from: {file.name}")
    
    video_files.sort(key=lambda x: x[1])
    
    if not video_files:
        logger.warning(f"No video files found in {season_dir.name}")
        return
    
    logger.info(f"Found {len(video_files)} episodes in {season_dir.name}")
    
    # Show format breakdown
    format_counts = {}
    for video_path, ep_num in video_files:
        fmt = detect_source_format(video_path.name)
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    
    logger.info(f"Format breakdown: {format_counts}")
    
    # Process each episode
    success_count = 0
    fail_count = 0
    
    for video_path, ep_num in video_files:
        if process_episode(video_path, ep_num):
            success_count += 1
        else:
            fail_count += 1
    
    logger.info(f"\nSeason {season_dir.name} complete: {success_count} succeeded, {fail_count} failed")


def validate_directories() -> bool:
    """Validate that required directories exist."""
    required = ['shows_dir', 'fan_subs_dir']
    missing = []
    
    for dir_name in required:
        dir_path = DIRECTORIES.get(dir_name)
        if not dir_path or not dir_path.exists():
            missing.append(f"{dir_name}: {dir_path}")
    
    if missing:
        logger.error("Missing required directories:")
        for m in missing:
            logger.error(f"  - {m}")
        return False
    
    # Check optional directories
    optional = ['bb_subs_dir']
    for dir_name in optional:
        dir_path = DIRECTORIES.get(dir_name)
        if not dir_path or not dir_path.exists():
            logger.warning(f"Optional directory not found: {dir_name}: {dir_path}")
    
    return True


def main():
    """Main processing function."""
    logger.info("="*60)
    logger.info("Detective Conan Archival Project - Subtitle Processing V2")
    logger.info("="*60)
    
    # Validate directories
    if not validate_directories():
        logger.error("Directory validation failed. Please check your config.yaml")
        return
    
    # Check for FFmpeg & FFSubSync
    try:
        result = subprocess.run(["ffs", "--version"], capture_output=True, text=True)
        logger.info(f"FFSubSync: Available")
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
    shows_dir = DIRECTORIES['shows_dir']
    season_dirs = sorted([d for d in shows_dir.iterdir() if d.is_dir() and "Season" in d.name])
    logger.info(f"\nFound {len(season_dirs)} season directories\n")
    
    if not season_dirs:
        logger.warning(f"No season directories found in {shows_dir}")
        logger.info("Expected directories named like 'Season 01', 'Season 02', etc.")
        return
    
    # Iterate through each season
    total_success = 0
    total_fail = 0
    
    for season_dir in season_dirs:
        process_season(season_dir)
    
    # Final cleanup
    cleanup_temp_files()
    
    logger.info("\n" + "="*60)
    logger.info("Processing Complete!")
    logger.info("="*60)


if __name__ == "__main__":
    main()