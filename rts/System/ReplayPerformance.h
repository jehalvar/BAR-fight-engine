/* This file is part of the Spring engine (GPL v2 or later), see LICENSE.html */

#pragma once

#include <atomic>

// Experimental BAR Fight options. Configured before loading a headless local
// replay, never changed by Lua or during a game. Shared engineSim sees the same
// state as the headless executable; no target-dependent inline definitions.
namespace ReplayPerformance {

enum Option: unsigned {
	MODEL_UNIFORMS = 1u << 0,
	TRANSFORM_UPLOAD_DIRTY = 1u << 1,
	FEATURE_ROTATION = 1u << 2,
	ANIMATION_QUEUE = 1u << 3,
	ANIMATION_ORDER = 1u << 4,
	PATH_SCANS = 1u << 5,
	TEXTURE_ASSEMBLY = 1u << 6,
	OFFLINE_PLAYBACK = 1u << 7,
};

inline std::atomic<unsigned> options{0};

inline bool Enabled(Option option) { return (options.load(std::memory_order_relaxed) & option) != 0; }
inline bool SkipModelUniforms() { return Enabled(MODEL_UNIFORMS); }
inline bool SkipTransformUploadDirty() { return Enabled(TRANSFORM_UPLOAD_DIRTY); }
inline bool CacheFeatureRotation() { return Enabled(FEATURE_ROTATION); }
inline bool ReuseAnimationQueue() { return Enabled(ANIMATION_QUEUE); }
inline bool CacheAnimationOrder() { return Enabled(ANIMATION_ORDER); }
inline bool PartitionPathScans() { return Enabled(PATH_SCANS); }
inline bool SkipTextureAssembly() { return Enabled(TEXTURE_ASSEMBLY); }
inline bool OfflinePlayback() { return Enabled(OFFLINE_PLAYBACK); }

}
