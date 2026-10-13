import { Suspense, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";

function Shape({ kind, color }) {
  const ref = useRef();
  useFrame((_, delta) => {
    if (ref.current) {
      ref.current.rotation.x += delta * 0.35;
      ref.current.rotation.y += delta * 0.55;
    }
  });

  const geometry = {
    box: <boxGeometry args={[1, 1, 1]} />,
    torus: <torusGeometry args={[0.62, 0.24, 16, 48]} />,
    octa: <octahedronGeometry args={[0.85, 0]} />,
    cone: <coneGeometry args={[0.72, 1.2, 4]} />,
  }[kind];

  return (
    <mesh ref={ref}>
      {geometry}
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.35}
        roughness={0.35}
        metalness={0.25}
      />
    </mesh>
  );
}

export default function Icon3D({ kind = "box", color = "#2F6F4E" }) {
  return (
    <div className="w-12 h-12">
      <Canvas camera={{ position: [1.6, 1.4, 2.2], fov: 40 }} dpr={[1, 1.5]} gl={{ alpha: true }}>
        <Suspense fallback={null}>
          <ambientLight intensity={0.7} />
          <directionalLight position={[2, 3, 2]} intensity={1} />
          <Shape kind={kind} color={color} />
        </Suspense>
      </Canvas>
    </div>
  );
}
