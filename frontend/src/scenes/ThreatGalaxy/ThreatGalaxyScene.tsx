'use client';

import React, { useRef, useState, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { useCyberStore } from '../../store/useCyberStore';

interface AgentNodeProps {
  name: string;
  position: [number, number, number];
  color: string;
  status: 'IDLE' | 'PROCESSING' | 'COMPLETED';
}

function AgentNode3D({ name, position, color, status }: AgentNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  
  useFrame((state) => {
    if (meshRef.current) {
      const time = state.clock.getElapsedTime();
      meshRef.current.rotation.y += 0.01;
      meshRef.current.rotation.x += 0.005;
      
      if (status === 'PROCESSING') {
        const pulse = 1.0 + Math.sin(time * 8) * 0.15;
        meshRef.current.scale.set(pulse, pulse, pulse);
      } else {
        const hoverScale = hovered ? 1.2 : 1.0;
        meshRef.current.scale.set(hoverScale, hoverScale, hoverScale);
      }
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <dodecahedronGeometry args={[status === 'PROCESSING' ? 0.95 : 0.8, 1]} />
        <meshStandardMaterial
          color={color}
          wireframe
          emissive={color}
          emissiveIntensity={status === 'PROCESSING' ? 2.5 : hovered ? 1.5 : 0.6}
          roughness={0.1}
          metalness={0.9}
        />
      </mesh>
      
      {status === 'PROCESSING' && (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.2, 1.3, 32]} />
          <meshBasicMaterial color={color} side={THREE.DoubleSide} transparent opacity={0.6} />
        </mesh>
      )}
    </group>
  );
}

interface LaserProps {
  start: [number, number, number];
  end: [number, number, number];
  color: string;
  active: boolean;
}

function LaserBeam3D({ start, end, color, active }: LaserProps) {
  const lineRef = useRef<THREE.LineSegments>(null);

  useFrame((state) => {
    if (lineRef.current && active) {
      const time = state.clock.getElapsedTime();
      const material = lineRef.current.material as THREE.LineBasicMaterial;
      material.opacity = 0.5 + Math.sin(time * 15) * 0.4;
    }
  });

  const points = useMemo(() => [new THREE.Vector3(...start), new THREE.Vector3(...end)], [start, end]);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  return (
    <lineSegments ref={lineRef} geometry={geometry}>
      <lineBasicMaterial
        color={color}
        transparent
        opacity={active ? 0.9 : 0.2}
        linewidth={active ? 2 : 1}
      />
    </lineSegments>
  );
}

function DriftingCodeNodes() {
  const pointsRef = useRef<THREE.Points>(null);
  const particleCount = 180;
  
  const positions = useMemo(() => {
    const arr = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {
      arr[i] = (Math.random() - 0.5) * 35;
      arr[i + 1] = (Math.random() - 0.5) * 30;
      arr[i + 2] = (Math.random() - 0.5) * 35;
    }
    return arr;
  }, []);

  useFrame((state) => {
    if (pointsRef.current) {
      const time = state.clock.getElapsedTime();
      pointsRef.current.rotation.y = time * 0.02;
      pointsRef.current.rotation.x = time * 0.01;
    }
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        color="#00f3ff"
        size={0.15}
        transparent
        opacity={0.65}
        sizeAttenuation
      />
    </points>
  );
}

export default function ThreatGalaxyScene() {
  const agents = useCyberStore((state) => state.agents);
  const phase = useCyberStore((state) => state.phase);

  const nodePositions: Record<string, { pos: [number, number, number]; color: string }> = useMemo(() => ({
    "Orchestrator AI": { pos: [0, 0, 0], color: '#00f3ff' },
    "Code Analysis Agent": { pos: [-5, 3.5, -2], color: '#ff007f' },
    "Security Review Agent": { pos: [5, 3.5, 2], color: '#8a2be2' },
    "Threat Intelligence Agent": { pos: [6, -2, -3], color: '#eab308' },
    "Machine Learning Agent": { pos: [-6, -2.5, 3], color: '#22c55e' },
    "Report Agent": { pos: [0, -5, 1], color: '#a855f7' },
  }), []);

  return (
    <div className="w-full h-full relative bg-[#030308]">
      <div className="absolute top-4 left-4 z-10 pointer-events-none">
        <div className="text-[10px] text-teal-400 font-mono tracking-widest border border-teal-500/20 px-2.5 py-1 bg-black/60 rounded">
          SECTOR: INTEL_CORE_07 // STAGE: {phase.toUpperCase()}
        </div>
      </div>

      <Canvas camera={{ position: [0, 2, 12], fov: 60 }}>
        <ambientLight intensity={0.15} />
        <pointLight position={[10, 10, 10]} intensity={1.5} />
        <pointLight position={[-10, -10, -10]} intensity={0.8} />

        <DriftingCodeNodes />
        <Stars radius={100} depth={50} count={300} factor={4} saturation={0.5} fade speed={1.5} />

        {Object.entries(nodePositions).map(([name, data]) => {
          const telemetry = agents[name] || { status: 'IDLE' };
          return (
            <AgentNode3D
              key={name}
              name={name}
              position={data.pos}
              color={data.color}
              status={telemetry.status}
            />
          );
        })}

        {Object.entries(nodePositions).map(([name, data]) => {
          if (name === "Orchestrator AI") return null;
          const telemetry = agents[name] || { status: 'IDLE' };
          const isActive = telemetry.status === 'PROCESSING' || phase !== 'idle';
          return (
            <LaserBeam3D
              key={`link-${name}`}
              start={nodePositions["Orchestrator AI"].pos}
              end={data.pos}
              color={data.color}
              active={isActive}
            />
          );
        })}

        <OrbitControls
          enableZoom={true}
          enablePan={false}
          maxDistance={22}
          minDistance={6}
          autoRotate={phase === 'idle'}
          autoRotateSpeed={0.35}
        />
      </Canvas>
    </div>
  );
}
