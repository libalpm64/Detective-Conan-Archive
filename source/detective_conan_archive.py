#!/usr/bin/env python3
"""Detective Conan Archival Project - Subtitle Processing"""

import os
import re
import subprocess
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    subprocess.run(["pip", "install", "pyyaml"], check=True)
    import yaml

# === Configuration ===

DEFAULT_CONFIG = {
    'skip_dubbed_episodes': False,
    'dubbed_episodes': [],
    'subtitle_labels': {'fan_subs': 'Fan Subs [English]', 'bb_subs': 'BB Subs [English]'},
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

def load_config() -> Dict:
    """Load and merge configuration from YAML file."""
    config_paths = [Path.cwd() / "config.yaml", Path.cwd() / "config.yml",
                    Path(__file__).parent / "config.yaml", Path(__file__).parent / "config.yml"]
    
    for path in config_paths:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded config from {path}")
                # Merge with defaults
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                    elif isinstance(value, dict) and isinstance(config.get(key), dict):
                        for k, v in value.items():
                            config[key].setdefault(k, v)
                return config
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
    
    logger.warning("No config file found, using defaults")
    return DEFAULT_CONFIG.copy()


def setup_directories(config: Dict) -> Dict[str, Path]:
    """Resolve directory paths from configuration."""
    dirs = config.get('directories', {})
    base = Path(dirs.get('base_dir', Path.cwd()))
    
    def resolve(key: str, default: str) -> Path:
        p = Path(dirs.get(key) or default)
        return p if p.is_absolute() else base / p
    
    result = {
        'base_dir': base,
        'shows_dir': resolve('shows_dir', 'Shows'),
        'fan_subs_dir': resolve('fan_subs_dir', 'fan subs 0001-0757'),
        'bb_subs_dir': resolve('bb_subs_dir', '[Fabre-RAW] Detective Conan Remastered [NetflixJP] [1080p]'),
        'temp_dir': resolve('temp_dir', 'temp_processing'),
        'ffmpeg_dir': Path(dirs['ffmpeg_dir']) if dirs.get('ffmpeg_dir') else None
    }
    return result


def setup_logging(config: Dict, log_dir: Path):
    """Configure logging handlers."""
    level = getattr(logging, config.get('log_level', 'INFO').upper(), logging.INFO)
    log_path = log_dir / config.get('log_file', 'processing.log')
    
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    
    logger.setLevel(level)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    for handler in [logging.FileHandler(log_path, encoding='utf-8'), logging.StreamHandler()]:
        handler.setLevel(level)
        handler.setFormatter(fmt)
        logger.addHandler(handler)


def find_ffmpeg(directories: Dict) -> Tuple[str, str]:
    """Locate FFmpeg binaries."""
    search_paths = [directories.get('ffmpeg_dir')] if directories.get('ffmpeg_dir') else []
    search_paths += [Path(r"C:\Program Files\ffmpeg\bin"), Path(r"C:\ffmpeg\bin"), directories['base_dir']]
    
    for p in search_paths:
        if p and p.exists():
            ffmpeg = p / "ffmpeg.exe"
            if ffmpeg.exists():
                return str(ffmpeg), str(p / "ffprobe.exe")
    
    return "ffmpeg", "ffprobe"


# Initialize globals
CONFIG = load_config()
DIRS = setup_directories(CONFIG)
setup_logging(CONFIG, DIRS['base_dir'])
FFMPEG, FFPROBE = find_ffmpeg(DIRS)
DIRS['temp_dir'].mkdir(exist_ok=True)

logger.info(f"Directories: Shows={DIRS['shows_dir']}, FanSubs={DIRS['fan_subs_dir']}, BBSubs={DIRS['bb_subs_dir']}")
logger.info(f"FFmpeg: {FFMPEG}")

# === Source Detection ===

SOURCE_PATTERNS = [
    ("erai-raws", lambda f: "[Erai-raws] Detective Conan -" in f and "[Multiple Subtitle]" in f),
    ("reghost-fabre", lambda f: "[RAW Reghost-Fabre]" in f),
    ("crunchyroll", lambda f: "[Crunchyroll]" in f),
    ("fabre-remastered", lambda f: "[Fabre-RAW] Detective Conan Remastered" in f),
    ("fabre", lambda f: "[Fabre-RAW] Detective Conan" in f),
    ("bilibili", lambda f: "bilibili" in f.lower()),
]

def detect_source(filename: str) -> str:
    """Identify video source format."""
    for name, check in SOURCE_PATTERNS:
        if check(filename):
            return name
    return "unknown"


EPISODE_PATTERNS = [
    r'\[Erai-raws\] Detective Conan - (\d{4})',
    r'\[RAW Reghost-Fabre\] Detective Conan (\d{1,4})',
    r'\[Crunchyroll\] Detective Conan - (\d{1,4})',
    r'\[Fabre-RAW\] Detective Conan (?:Remastered )?(\d{4})',
    r'Detective Conan (\d{4})',
]

def extract_episode(filename: str) -> Optional[int]:
    """Extract episode number from filename."""
    for pattern in EPISODE_PATTERNS:
        if match := re.search(pattern, filename):
            return int(match.group(1))
    return None


# === Subtitle Handling ===

def get_subtitle_path(ep: int, sub_type: str) -> Optional[Path]:
    """Get subtitle file path for episode."""
    if sub_type == "fan" and 1 <= ep <= 757:
        path = DIRS['fan_subs_dir'] / f"{ep:04d}.ass"
        return path if path.exists() else None
    
    if sub_type == "bb" and 124 <= ep <= 753:
        prefix = "Remastered " if ep <= 173 else ""
        path = DIRS['bb_subs_dir'] / f"[Fabre-RAW] Detective Conan {prefix}{ep:04d} [NetflixJP] [1080p].srt"
        return path if path.exists() else None
    
    return None


def sync_subtitle(video: Path, sub_in: Path, sub_out: Path) -> bool:
    """Sync subtitle timing using ffsubsync."""
    try:
        logger.info(f"Syncing: {sub_in.name}")
        result = subprocess.run(
            ["ffs", str(video), "-i", str(sub_in), "-o", str(sub_out)],
            capture_output=True, text=True, timeout=CONFIG.get('ffsubsync_timeout', 45)
        )
        if result.returncode == 0:
            logger.info(f"Synced: {sub_out.name}")
            return True
        logger.warning(f"Sync failed, using original")
    except subprocess.TimeoutExpired:
        logger.warning("Sync timeout, using original")
    except Exception as e:
        logger.error(f"Sync error: {e}")
    
    shutil.copy2(sub_in, sub_out)
    return False


# === Episode Configuration ===

def get_episode_config(ep: int, source: str) -> Dict:
    """Get processing configuration for episode."""
    # Skip BiliBili - already has embedded subs
    if source == "bilibili":
        return {'skip': True, 'message': 'BiliBili file - subs already embedded'}
    
    # Erai-raws 1-123: rename only
    if source == "erai-raws" and 1 <= ep <= 123:
        return {'rename_only': True, 'output_format': 'remastered'}
    
    # Episode ranges
    if 1 <= ep <= 123:
        return CONFIG.get('episodes_1_123', {'keep_existing': True, 'fan': True, 'bb': False})
    elif 124 <= ep <= 753:
        return CONFIG.get('episodes_124_753', {'keep_existing': False, 'fan': True, 'bb': True})
    else:  # 754+
        return CONFIG.get('episodes_754_1132', {'keep_existing': True, 'fan': True, 'bb': False})


def get_output_name(ep: int, source: str, config: Dict) -> str:
    """Generate output filename."""
    fmt = config.get('output_format')
    if fmt == 'remastered' or source in ('erai-raws', 'fabre', 'fabre-remastered'):
        return f"Detective Conan Remastered {ep:04d} [1080p].mkv"
    if fmt == '480p' or source == 'reghost-fabre':
        return f"Detective Conan {ep:04d} [480p].mkv"
    return f"Detective Conan Remastered {ep:04d} [1080p].mkv"


# === Muxing ===

def mux_subtitles(video: Path, fan_sub: Optional[Path], bb_sub: Optional[Path], 
                  output: Path, config: Dict) -> bool:
    """Mux video with subtitle tracks."""
    try:
        ep = extract_episode(video.name)
        logger.info(f"Muxing episode {ep}")
        
        cmd = [FFMPEG, "-i", str(video)]
        maps = ["-map", "0:v", "-map", "0:a"]
        metadata = []
        input_idx = 1
        sub_idx = 0
        
        # Keep existing subs
        if config.get('keep_existing', False):
            maps.extend(["-map", "0:s?"])
            sub_idx = 1
        
        labels = CONFIG.get('subtitle_labels', {})
        
        # Add fan subs
        if fan_sub and fan_sub.exists() and config.get('fan', True):
            cmd.extend(["-i", str(fan_sub)])
            maps.extend(["-map", f"{input_idx}:s"])
            metadata.extend([f"-metadata:s:s:{sub_idx}", "language=eng",
                           f"-metadata:s:s:{sub_idx}", f"title={labels.get('fan_subs', 'Fan Subs')}"])
            input_idx += 1
            sub_idx += 1
        
        # Add BB subs
        if bb_sub and bb_sub.exists() and config.get('bb', True):
            cmd.extend(["-i", str(bb_sub)])
            maps.extend(["-map", f"{input_idx}:s"])
            metadata.extend([f"-metadata:s:s:{sub_idx}", "language=eng",
                           f"-metadata:s:s:{sub_idx}", f"title={labels.get('bb_subs', 'BB Subs')}"])
        
        cmd.extend(maps + metadata + ["-c:v", "copy", "-c:a", "copy", "-c:s", "copy", "-y", str(output)])
        
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                               errors='replace', timeout=CONFIG.get('ffmpeg_timeout', 300))
        
        if result.returncode == 0:
            logger.info(f"Muxed: {output.name}")
            return True
        
        logger.error(f"Mux failed: {result.stderr[-500:] if result.stderr else 'No output'}")
        return False
        
    except subprocess.TimeoutExpired:
        logger.error(f"Mux timeout for {video.name}")
    except Exception as e:
        logger.error(f"Mux error: {e}")
    return False


# === Processing ===

def process_episode(video: Path, ep: int) -> bool:
    """Process a single episode."""
    try:
        logger.info(f"\n{'='*50}\nProcessing Episode {ep}: {video.name}\n{'='*50}")

        source = detect_source(video.name)
        logger.info(f"Source: {source}")

        config = get_episode_config(ep, source)

        output_name = get_output_name(ep, source, config)
        output = video.parent / output_name

        if source == "bilibili":
            if video.name != output_name:
                logger.info(f"Renaming BiliBili file: {video.name} -> {output_name}")
                try:
                    if output.exists():
                        logger.warning(f"Target already exists: {output}. Overwriting.")
                        output.unlink()
                    video.rename(output)
                except Exception as e:
                    logger.error(f"Failed to rename BiliBili file: {e}")
                    return False
            else:
                logger.info("BiliBili file already in desired format")
            return True

        if config.get('skip'):
            logger.info(f"Skipping: {config.get('message', 'configured to skip')}")
            return True

        if CONFIG.get('skip_dubbed_episodes') and ep in set(CONFIG.get('dubbed_episodes', [])):
            logger.info("Dubbed episode, skipping processing")
            if video.name != output_name:
                try:
                    if output.exists():
                        logger.warning(f"Target already exists: {output}. Overwriting.")
                        output.unlink()
                    video.rename(output)
                except Exception as e:
                    logger.error(f"Failed to rename dubbed episode: {e}")
                    return False
            return True

        if config.get('rename_only'):
            if video.name != output_name:
                logger.info(f"Renaming: {video.name} -> {output_name}")
                try:
                    if output.exists():
                        logger.warning(f"Target already exists: {output}. Overwriting.")
                        output.unlink()
                    video.rename(output)
                except Exception as e:
                    logger.error(f"Rename failed: {e}")
                    return False
            logger.info(f"[OK] Episode {ep}")
            return True

        fan_orig = get_subtitle_path(ep, "fan") if config.get('fan') else None
        bb_orig = get_subtitle_path(ep, "bb") if config.get('bb') else None

        if fan_orig:
            logger.info(f"Fan subs: {fan_orig.name}")
        if bb_orig:
            logger.info(f"BB subs: {bb_orig.name}")

        if not fan_orig and not bb_orig:
            if config.get('keep_existing'):
                logger.info("No new subs, keeping existing")
                if video.name != output_name:
                    try:
                        if output.exists():
                            logger.warning(f"Target already exists: {output}. Overwriting.")
                            output.unlink()
                        video.rename(output)
                    except Exception as e:
                        logger.error(f"Failed to rename while keeping existing subs: {e}")
                        return False
                return True
            logger.warning(f"No subtitles found for episode {ep}")
            return False

        temp = DIRS['temp_dir']
        temp.mkdir(parents=True, exist_ok=True)
        fan_synced = bb_synced = None

        if fan_orig:
            fan_synced = temp / f"{ep:04d}_fan.ass"
            sync_subtitle(video, fan_orig, fan_synced)

        if bb_orig:
            bb_synced = temp / f"{ep:04d}_bb.srt"
            sync_subtitle(video, bb_orig, bb_synced)

        temp_out = temp / f"temp_{ep:04d}.mkv"
        success = mux_subtitles(video, fan_synced, bb_synced, temp_out, config)

        if success and temp_out.exists():
            try:
                video.unlink()
                if output.exists():
                    logger.warning(f"Final target already exists ({output}), overwriting.")
                    output.unlink()
                shutil.move(str(temp_out), str(output))
                logger.info(f"[OK] Episode {ep}")
            except Exception as e:
                logger.error(f"Failed to finalize muxed file for episode {ep}: {e}")
                return False

            for f in (fan_synced, bb_synced):
                if f and f.exists():
                    try:
                        f.unlink()
                    except Exception:
                        logger.debug(f"Could not remove temp file: {f}")
            return True

        logger.error(f"[FAIL] Episode {ep}")
        return False

    except Exception as e:
        logger.error(f"Error processing episode {ep}: {e}")
        return False



def process_season(season_dir: Path):
    """Process all episodes in a season directory."""
    logger.info(f"\n{'#'*50}\nProcessing: {season_dir.name}\n{'#'*50}")
    
    episodes = [(f, extract_episode(f.name)) for f in season_dir.glob("*.mkv")]
    episodes = [(f, ep) for f, ep in episodes if ep is not None]
    episodes.sort(key=lambda x: x[1])
    
    if not episodes:
        logger.warning(f"No episodes found in {season_dir.name}")
        return
    
    logger.info(f"Found {len(episodes)} episodes")
    
    # Format breakdown
    formats = {}
    for f, _ in episodes:
        fmt = detect_source(f.name)
        formats[fmt] = formats.get(fmt, 0) + 1
    logger.info(f"Formats: {formats}")
    
    success = sum(1 for f, ep in episodes if process_episode(f, ep))
    logger.info(f"\n{season_dir.name}: {success}/{len(episodes)} succeeded")


def validate_setup() -> bool:
    """Validate required directories and tools exist."""
    missing = [name for name in ['shows_dir', 'fan_subs_dir'] 
               if not DIRS.get(name) or not DIRS[name].exists()]
    
    if missing:
        logger.error(f"Missing directories: {missing}")
        return False
    
    if not DIRS.get('bb_subs_dir') or not DIRS['bb_subs_dir'].exists():
        logger.warning(f"BB subs directory not found: {DIRS.get('bb_subs_dir')}")
    
    # Check tools
    try:
        subprocess.run(["ffs", "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        logger.error("FFSubSync not found! pip install ffsubsync")
        return False
    
    try:
        subprocess.run([FFMPEG, "-version"], capture_output=True, text=True)
    except FileNotFoundError:
        logger.error(f"FFmpeg not found: {FFMPEG}")
        return False
    
    return True


def cleanup():
    """Remove temporary files."""
    if not CONFIG.get('cleanup_temp_files', True):
        return
    try:
        for f in DIRS['temp_dir'].glob("*"):
            if f.is_file():
                f.unlink()
        logger.info("Cleaned temp files")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")


def main():
    """Main entry point."""
    logger.info("="*50)
    logger.info("Detective Conan Archival Project")
    logger.info("="*50)
    
    if not validate_setup():
        return
    
    seasons = sorted([d for d in DIRS['shows_dir'].iterdir() 
                      if d.is_dir() and "Season" in d.name])
    
    if not seasons:
        logger.warning(f"No season directories in {DIRS['shows_dir']}")
        return
    
    logger.info(f"Found {len(seasons)} seasons")
    
    for season in seasons:
        process_season(season)
    
    cleanup()
    logger.info("\n" + "="*50 + "\nComplete!\n" + "="*50)

if __name__ == "__main__":
    main()