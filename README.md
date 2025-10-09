# 🎯 Bullseye Injector

A revolutionary sprite injection system for PokeMMO that uses the Bullseye mod as a foundation to create custom sprite mods while preserving type weakness badges.

## ❓ What is Bullseye Injector?

**Bullseye Injector** transforms how you create PokeMMO sprite mods. Instead of manually editing sprites, it uses the proven **Bullseye mod** (which adds type weakness badges) as a library to intelligently inject your custom sprites.

### Key Innovation
- **Uses Bullseye as Foundation**: Leverages the existing Bullseye mod's type weakness badge system
- **Full Sprite Swaps**: Complete sprite replacement while maintaining badge functionality  
- **Automatic Processing**: Handles gender variants, case sensitivity, and file compatibility
- **Professional Output**: Creates ready-to-install PokeMMO mod files

## ✨ Features

### Core Functionality
- **Smart Sprite Injection**: Uses Bullseye mod as foundation to inject custom sprites
- **Type Weakness Badge Preservation**: Maintains all Bullseye mod functionality while swapping sprites
- **Automatic Back Sprite Processing**: Processes and positions back sprites to match front sprite layouts
- **Professional Mod Compiler**: Built-in mod packaging system with metadata management
- **Batch Processing**: Process entire sprite collections at once

### Advanced Features
- **Quality Preservation**: Canvas expansion system prevents quality loss from downsampling
- **Gender Variant Support**: Automatic detection and processing of male/female sprite variants
- **Case-Insensitive Matching**: Handles different filename conventions automatically
- **Cross-Platform Compatibility**: Works on Windows, Linux, and macOS
- **Real-time Preview**: See processed sprites before final output
- **Comprehensive Validation**: Multi-pass analysis for file compatibility and missing variants
- **Smart File Detection**: Background analysis with animated progress indicators
- **Duplicate Detection**: Prevents conflicts and identifies redundant files
- **Malformed File Fixes**: Automatically corrects common filename issues (.gif.gif, ..gif, etc.)
- **Animation Preservation**: Maintains GIF timing, disposal methods, and loop information
- **Memory Optimization**: LRU caching system for efficient preview handling
- **Threaded Processing**: Non-blocking UI during file analysis and sprite processing

### Scaling Configuration
- **Default Scaling Values**: Set base scaling for summary, front, and back sprites
- **Individual Overrides**: Override scaling for specific Pokemon with precision controls
- **Real-time Configuration**: Changes save automatically and persist across sessions
- **Pokemon Detection**: Only shows Pokemon that exist in your sprite collection
- **Range Support**: Handles Pokemon #001-1024 with dynamic detection

## 🚀 Quick Start

### Installation
1. Download the latest release or build from source
2. Extract to your desired location
3. Run `BullseyeInjector.exe` (Windows) or `python sprite_converter_gui.py` (source)

### Basic Usage
1. **Set Directories**:
   - **Bullseye Sprites**: Path to your Bullseye mod sprites
   - **Replacement Sprites**: Path to your custom sprites
   - **Output Directory**: Where to save the final mod

2. **Configure Settings**:
   - **Process All**: Process entire sprite collection
   - **Limit**: Process only specific Pokemon (e.g., "001-050" for first 50)
   - **Show Logs**: Display detailed processing information

3. **Build Your Mod**:
   - Click **"Build Mod"** to open the configuration dialog
   - Set mod name, version, authors, and description
   - Configure sprite scaling (optional)
   - Click **"Build Mod"** to create your .mod file

## 📁 Directory Structure

### Required Files
```
Your Project/
├── BullseyeInjector.exe          # Main application
├── Template.zip                  # Bullseye mod template
├── Bullseye Sprites/             # Your Bullseye mod sprites
│   └── sprites/battlesprites/
│       ├── 001-front-n.gif
│       ├── 001-back-n.gif
│       └── ...
└── Custom Sprites/               # Your replacement sprites
    ├── 001-front-n.gif
    ├── 001-back-n.gif
    └── ...
```

### Output Structure
```
Output/
├── 001-front-n.gif              # Processed sprites
├── 001-back-n.gif
├── YourModName.mod              # Final mod file
└── logs/
    └── process.log              # Detailed processing log
```

## 🎮 Sprite Scaling System

### How It Works
The scaling system controls how sprites appear in-game:
- **Summary Scale**: Controls sprite size in Pokemon summary screens
- **Front Scale**: Controls sprite size when facing forwards (your Pokemon)
- **Back Scale**: Controls sprite size when facing backwards (opponent's Pokemon)

### Configuration Options
- **Default Values**: Set base scaling for all Pokemon
- **Individual Overrides**: Override specific Pokemon with custom values
- **Detection Threshold**: Configure what constitutes a "custom sprite" (default: 1.10x larger)
- **Range**: 0.0 to 10.0 (recommended: 1.0-3.0)

### Example Usage
- **Default Summary Scale**: 2.7 (good for most sprites)
- **Default Front Scale**: 1.0 (standard size)
- **Default Back Scale**: 1.0 (standard size)
- **Override Pokemon #150**: Set to 0.8 for smaller appearance

## 🔍 Analysis & Validation Features

### Comprehensive File Analysis
- **Multi-Level Matching**: Direct matches, case-insensitive, normalized, and cross-type matching
- **Gender Variant Detection**: Automatically identifies male/female sprite variants (-m/-f suffixes)
- **Missing File Analysis**: Identifies missing sprites with source file suggestions
- **Duplicate Detection**: Prevents conflicts using signature-based duplicate identification
- **Malformed File Correction**: Fixes common issues like double extensions (.gif.gif → .gif)

### Validation Engine
- **Phase 1**: Simple fixes (case corrections, extension fixes, malformed files)
- **Phase 2**: Missing file analysis with intelligent source identification
- **Phase 2.5**: Back file detection for all front files
- **Phase 3**: Cleanup of unnecessary files and optimization
- **Deduplication**: Signature-based duplicate detection with conflict prevention

### Smart Recommendations
- **File Operations**: rename, clone, create_gender_variant, create_base_from_male/female, remove_base, cleanup
- **Priority System**: Organized operation priority to prevent conflicts
- **Retry Mechanism**: 3 attempts for permission errors with 1-second delays
- **Conflict Resolution**: Intelligent handling of duplicate files and naming conflicts

## 🆚 Feature Comparison

| Feature | Traditional Manual Editing | Bullseye Injector |
|---------|---------------------------|-------------------|
| **Badge Preservation** | ❌ Manual recreation | ✅ Automatic preservation |
| **Quality Loss** | ❌ Often occurs | ✅ Canvas expansion prevents loss |
| **Gender Variants** | ❌ Manual handling | ✅ Automatic detection |
| **Batch Processing** | ❌ One at a time | ✅ Entire collections |
| **Mod Creation** | ❌ Manual packaging | ✅ One-click generation |
| **Time Investment** | ❌ Hours per sprite | ✅ Minutes per collection |

## 🏗️ Technical Overview

### Core Components
- **Image Processing Engine**: Smart component detection separates sprites from badges using flood-fill algorithms
- **GUI Framework**: Modern dark-themed interface with real-time preview and threaded processing
- **Mod Packaging System**: Creates professional PokeMMO-compatible mod files with proper metadata
- **Validation Engine**: Multi-pass analysis with comprehensive file compatibility checking
- **Scaling System**: Advanced configuration with default values and individual Pokemon overrides

### Processing Capabilities
- **Component Detection**: Automatically identifies and separates Pokemon sprites from type weakness badges
- **Canvas Expansion**: Preserves sprite quality by expanding canvas instead of downsampling
- **Animation Handling**: Maintains GIF timing, disposal methods, and loop information
- **Batch Processing**: Handles entire sprite collections (1000+ files) efficiently
- **Memory Management**: LRU caching system with automatic cleanup
- **Error Recovery**: Retry mechanisms for file permission issues

### Supported Formats
- **Input**: GIF and PNG files with full transparency support
- **Output**: Optimized GIF files with complete animation preservation
- **Mod Format**: Standard PokeMMO .mod files with proper structure
- **Configuration**: JSON-based settings with persistent storage

### File Naming Convention
Standard format: `XXX-direction-variant-gender.ext`
- **XXX**: Three-digit Pokemon number (001-1024)
- **direction**: front, back, normal
- **variant**: n (normal), s (shiny)
- **gender**: m (male), f (female), or omitted
- **ext**: gif or png

## 🔧 Configuration

### Settings File (`sprite_converter_settings.json`)
The app automatically saves your preferences:
```json
{
  "move_dir": "path/to/bullseye/sprites",
  "sprite_dir": "path/to/replacement/sprites", 
  "output_dir": "path/to/output",
  "log_dir": "logs",
  "use_custom_log_dir": false,
  "process_all": true,
  "show_logs": true,
  "limit": "",
  "default_summary_scale": 2.7,
  "default_front_scale": 1.0,
  "default_back_scale": 1.0,
  "detection_threshold": 1.10,
  "summary_overrides": {"001": 3.0, "025": 2.5},
  "front_overrides": {"150": 0.8, "151": 0.9},
  "back_overrides": {"150": 0.6, "151": 0.7}
}
```

### Build Configuration
- **Mod Name**: Custom name for your mod
- **Version**: Semantic versioning (e.g., "1.0")
- **Authors**: Auto-includes "UncleTyrone, Zoruah" + custom authors
- **Description**: Custom mod description

## 🖥️ User Interface Features

### Modern Dark Theme
- **Color Scheme**: Professional dark theme with purple accents (#8e44ad)
- **Responsive Design**: Adapts to different window sizes and screen resolutions
- **Hover Effects**: Interactive feedback for buttons and controls
- **High Contrast**: Excellent readability with sufficient contrast ratios

### Real-time Features
- **Live Preview**: Cycles through last 10 processed sprites (800ms per sprite)
- **Progress Tracking**: Animated progress bars during file analysis and processing
- **Log Integration**: Real-time log display with color-coded messages
- **Status Updates**: Live status updates during all operations

### Interactive Elements
- **Directory Browsing**: Easy folder selection with browse buttons
- **Drag & Drop**: Support for dragging folders into directory fields
- **Keyboard Navigation**: Full keyboard support for all operations
- **Tooltips**: Helpful descriptions for complex operations and settings

### Advanced UI Capabilities
- **Lazy Loading**: Issues tabs load content on-demand to prevent startup lag
- **Debounced Search**: Search operations are optimized to prevent excessive filtering
- **Memory-efficient Display**: Only loads first frame of GIFs for preview cycling
- **Error Handling**: Clear, actionable error messages with suggested solutions

## 🔧 Troubleshooting

### Common Issues
- **"No matching sprite files found"**: Check filename convention (XXX-direction-variant-gender.ext)
- **Permission denied errors**: Close image viewers accessing the sprite files
- **Preview not showing**: Ensure processed sprites exist in output directory
- **Mod not working in-game**: Verify mod file structure and PokeMMO compatibility

### Debug Information
When reporting issues, include:
1. Log files from `logs/process.log`
2. Number of sprites being processed
3. Examples of problematic filenames
4. Operating system and available memory

## 📊 Performance

### Typical Results
Based on real usage data:
- **Mod File Size**: ~276 MB for complete sprite collection (Pokemon #001-711)
- **Processing Time**: Minutes for entire collections (1000+ sprites)
- **Quality**: No quality loss, canvas expansion preserves detail
- **Compatibility**: 100% PokeMMO compatible output
- **Memory Usage**: Efficient LRU caching with automatic cleanup
- **File Processing**: Background threaded analysis with progress indicators

### Performance Features
- **Batch Processing**: Handles entire sprite collections in single operations
- **Smart Caching**: LRU cache system with 50 image limit and automatic cleanup
- **Threaded Operations**: Non-blocking UI during file analysis and processing
- **Memory Management**: Proper cleanup of PIL images and tkinter objects
- **Progress Tracking**: Real-time progress bars and status updates
- **Error Recovery**: Automatic retry mechanisms for file permission issues

### Optimization Tips
- Use "Process All" for best performance with large collections
- Close other applications to free memory during processing
- Use SSD storage for faster file operations
- Enable "Show Logs" for detailed progress monitoring
- Use the limit option for testing with smaller sprite sets

## 🤝 Contributing

### Development Setup
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run from source: `python sprite_converter_gui.py`
4. Build executable: `python build_simple.py`

### Code Style
- Follow PEP 8 Python style guidelines
- Use type hints where appropriate
- Add comprehensive docstrings
- Include error handling and logging

## 📄 License

This tool is provided as-is for the PokeMMO community. Use responsibly and respect game terms of service.

## 🙏 Credits

Built for the PokeMMO community to revolutionize sprite modding by using the Bullseye mod as a library for intelligent sprite injection.

**Special Thanks**: 
- **UncleTyrone** - Creator of the Bullseye Injector project and the application you're looking at
- **Zoruah** - Original creator of the Bullseye mod and type weakness badge system
- The PokeMMO community for inspiration and feedback
- All contributors who helped make this system possible

## 📞 Getting Help

If you encounter issues:
1. Check the log output in the GUI
2. Look at the `logs/process.log` file for detailed information
3. Verify your directory structure matches the expected format
4. Review the troubleshooting section above

For additional support, please refer to the PokeMMO modding community forums or create an issue in the project repository.

---

**Bullseye Injector** - Making PokeMMO sprite modding accessible to everyone! 🎯