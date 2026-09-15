#!/bin/bash
# ~/.consciousness_engine/scripts/install_voice_presence.sh

echo "🎤 Installing Voice Presence Stack..."

# 1. Install dependencies
pip install sounddevice soundfile numpy
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 2. Install Silero VAD
mkdir -p ~/.cache/silero_vad
wget -O ~/.cache/silero_vad/silero_vad.jit \
    https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.jit

# 3. Install RNNoise (optional)
pip install rnnoise 2>/dev/null || echo "RNNoise not available, using fallback"

# 4. Copy presence script
cp ~/.consciousness_engine/voice/presence.py ~/.consciousness_engine/voice/

# 5. Test audio
python3 -c "import sounddevice as sd; print('✅ Audio devices:', sd.query_devices())"

echo "✅ Voice Presence installed"