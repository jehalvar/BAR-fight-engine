/* This file is part of the Spring engine (GPL v2 or later), see LICENSE.html */

#pragma once

#include <vector>

#include "NodeLayer.h"
#include "PathEnums.h"
#include "Path.h"
#include "System/UnorderedMap.hpp"
#include "System/Threading/SpringThreading.h"

#include "Registry.h"

#ifdef GetTempPath
#undef GetTempPath
#undef GetTempPathA
#endif

struct SRectangle;

namespace QTPFS {
	struct PathCache {

		struct DirtyPathDetail {
			QTPFS::entity pathEntity;
			int autoRepathTrigger;
			int nodesAreCleanFromNodeId;
			bool clearSharing;
			bool clearPath;
		};

		bool MarkDeadPaths(const SRectangle& r, const NodeLayer& nodeLayer);
		void BuildPathTypeSnapshot();
		void ClearPathTypeSnapshot();

		void Init(int pathTypes) {
			dirtyPaths.clear();
			dirtyPaths.resize(pathTypes);
			pathsByType.clear();
			pathsByType.resize(pathTypes);
			pathSnapshotActive = false;
		}

		void SetLayerPathCount(int pathType, int paths) {
			dirtyPaths[pathType].reserve(paths);
		}

		std::vector< std::vector<DirtyPathDetail> > dirtyPaths;

	private:
		// Rebuilt for each map-update worker phase. Only capacity survives frames;
		// no registry lifecycle hooks or persistent entity index are required.
		std::vector<std::vector<QTPFS::entity>> pathsByType;
		bool pathSnapshotActive = false;
	};
}
