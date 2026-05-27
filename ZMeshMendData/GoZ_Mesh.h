/*
 Copyright (c)2011 - Pixologic Inc. All rights reserved.

 All title and intellectual property rights in and to the SDK and any copies of the SDK,
 are owned by Licensor.
 All title and intellectual property rights in and to the content which may be accessed
 through use of the SDK is the property of the respective content owner and may be protected
 by applicable copyright or other intellectual property laws and treaties.
 This Agreement grants you no rights to use such content.

 NO WARRANTIES. Licensor expressly disclaims any warranty for the SDK.
 THE SDK AND ANY RELATED DOCUMENTATION IS PROVIDED «AS IS» WITHOUT WARRANTY OF ANY KIND,
 EITHER EXPRESS OR IMPLIED, INCLUDING, WITHOUT LIMITATION, THE IMPLIED WARRANTIES
 OR MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, OR NONINFRINGEMENT.
 THE ENTIRE RISK ARISING OUT OF USE OR PERFORMANCE OF THE SDK REMAINS WITH YOU.

 BY INSTALLING, COPYING, OR USING THE SDK, YOU AGREE TO BE BOUND BY THE TERMS OF THIS AGREEMENT.
 IF YOU DO NOT AGREE TO THE TERMS OF THIS AGREEMENT, DO NOT INSTALL OR USE THE SDK.
 */

#ifndef __GOZ_MESH_H__
#define __GOZ_MESH_H__

#include "GoZ_Utils.h"
#include <string>
#include <vector>

class GoZ_Mesh
{
public:
    GoZ_Mesh();
    ~GoZ_Mesh();
    void clear();
    bool readMesh(const char *fileName);
    bool writeMesh(const char *fileName);


public:
    std::string    m_name;
    std::string    m_material;
    unsigned int    m_flags;
    int             m_vertexCount;
    std::vector<float> m_vertices;
    int             m_faceCount;
    int             m_faceType;
    std::vector<int> m_vertexIndices;
    int             m_uvFaceType;
    std::vector<float> m_uvs;
    std::vector<unsigned short> m_mask;
    std::vector<unsigned int> m_mrgb;
    std::vector<short> m_groups;
    std::vector<char> m_crease;
    std::string    m_diffuseMap;
    std::string    m_normalMap;
    std::string    m_displacementMap;
    float           m_displacementScale;
};

#endif  // __GOZ_MESH_H__
