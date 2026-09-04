import React, { useRef, useEffect, useState } from 'react';
import Globe from 'react-globe.gl';

const IntroGlobe = () => {
  const globeEl = useRef();
  const [arcsData, setArcsData] = useState([]);
  
  // Cursor  starting position 
  const dragStartX = useRef(0);

  // Network lines generation 
  useEffect(() => {
    const N = 20;
    const arcs = [...Array(N).keys()].map(() => ({
      startLat: (Math.random() - 0.5) * 180,
      startLng: (Math.random() - 0.5) * 360,
      endLat: (Math.random() - 0.5) * 180,
      endLng: (Math.random() - 0.5) * 360,
      color: '#d942ff'
    }));
    setArcsData(arcs);
  }, []);

  // Controls Setup
  useEffect(() => {
    if (globeEl.current) {
      const controls = globeEl.current.controls();
      
      controls.autoRotate = true;
      controls.autoRotateSpeed = 2.0; // Default speed
      
      controls.enableZoom = false; // Zoom disabled
      controls.minPolarAngle = Math.PI / 2; // Up/Down locked
      controls.maxPolarAngle = Math.PI / 2; 

      // Naya: Isse dragging bahut smooth aur realistic (physics-based) ho jati hai
      controls.enableDamping = true;
      controls.dampingFactor = 0.05;

      globeEl.current.pointOfView({ altitude: 2.5 });
    }
  }, []);

  // Naya: Jab user click/touch start kare
  const handlePointerDown = (e) => {
    dragStartX.current = e.clientX; // X-axis par starting point save karo
  };

  // Naya: Jab user click/touch chhod de
  const handlePointerUp = (e) => {
    const dragEndX = e.clientX;
    const dragDistance = dragEndX - dragStartX.current;
    
    if (globeEl.current) {
      const controls = globeEl.current.controls();
      
      // Agar user ne right ki taraf drag kiya hai (distance positive hai)
      if (dragDistance > 10) {
        controls.autoRotateSpeed = 2.0; // Right ghumna shuru karega
      } 
      // Agar user ne left ki taraf drag kiya hai (distance negative hai)
      else if (dragDistance < -10) {
        controls.autoRotateSpeed = -2.0; // Left ghumna shuru karega
      }
    }
  };

  return (
    <div 
      style={styles.container}
      // Naya: Div par pointer events lagaye hain drag detect karne ke liye
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
    >
      <Globe
  ref={globeEl}
  backgroundColor="#050011"
  globeImageUrl="/globe.png" 
  atmosphereColor="#d942ff"
  atmosphereAltitude={0.2}
  arcsData={arcsData}
  arcColor={'color'}
  arcDashLength={0.4}
  arcDashGap={0.2}
  arcDashAnimateTime={1500}
  arcAltitudeAutoScale={0.3}
/>
    </div>
  );
};

const styles = {
  container: {
    width: '100vw',
    height: '100vh',
    margin: 0,
    padding: 0,
    overflow: 'hidden',
    position: 'relative',
    backgroundColor: '#050011',
    cursor: 'grab' // Cursor ko grab jaisa banata hai
  }
};

export default IntroGlobe;