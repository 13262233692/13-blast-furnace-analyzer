import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

const vertexShader = /* glsl */ `
  varying vec2 vUv;
  varying float vErosion;
  varying vec3 vNormal;
  varying vec3 vPosition;

  uniform float uTime;
  uniform sampler2D uErosionMap;
  uniform float uErosionIntensity;
  uniform float uBaseRadiusTop;
  uniform float uBaseRadiusBottom;
  uniform float uHeight;

  void main() {
    vUv = uv;
    vNormal = normal;

    float normalizedHeight = (position.y + uHeight * 0.5) / uHeight;

    float baseRadius = mix(uBaseRadiusBottom, uBaseRadiusTop, normalizedHeight);

    float theta = atan(position.z, position.x);
    float uCoord = (theta + 3.14159265) / (2.0 * 3.14159265);
    float vCoord = 1.0 - normalizedHeight;

    float erosion = texture2D(uErosionMap, vec2(uCoord, vCoord)).r;
    vErosion = erosion;

    float radialOffset = erosion * uErosionIntensity;
    float newRadius = baseRadius - radialOffset;

    vec3 newPosition = position;
    float currentRadius = length(position.xz);
    if (currentRadius > 0.001) {
      newPosition.xz = normalize(position.xz) * newRadius;
    }

    float pulse = sin(uTime * 2.0 + erosion * 6.2831) * 0.02 * erosion;
    newPosition.y += pulse * 0.3;

    vPosition = newPosition;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
`

const fragmentShader = /* glsl */ `
  varying vec2 vUv;
  varying float vErosion;
  varying vec3 vNormal;
  varying vec3 vPosition;

  uniform float uTime;
  uniform vec3 uLightPos;

  vec3 erosionColor(float e) {
    vec3 c0 = vec3(0.15, 0.45, 0.15);
    vec3 c1 = vec3(0.95, 0.82, 0.20);
    vec3 c2 = vec3(1.0, 0.35, 0.10);
    vec3 c3 = vec3(0.95, 0.10, 0.05);

    if (e < 0.25) {
      return mix(c0, c1, e / 0.25);
    } else if (e < 0.55) {
      return mix(c1, c2, (e - 0.25) / 0.30);
    } else {
      return mix(c2, c3, (e - 0.55) / 0.45);
    }
  }

  void main() {
    vec3 normal = normalize(vNormal);
    vec3 lightDir = normalize(uLightPos - vPosition);

    float diffuse = max(dot(normal, lightDir), 0.0);
    float ambient = 0.25;

    vec3 baseColor = erosionColor(vErosion);

    float glowIntensity = pow(vErosion, 2.5) * 1.5;
    float pulse = 0.5 + 0.5 * sin(uTime * 3.0 + vErosion * 10.0);
    vec3 glowColor = vec3(1.0, 0.3, 0.05) * glowIntensity * (0.6 + 0.4 * pulse);

    vec3 finalColor = baseColor * (ambient + diffuse * 0.8) + glowColor;

    float fresnel = pow(1.0 - abs(dot(normal, vec3(0.0, 0.0, 1.0))), 2.0);
    finalColor += vec3(0.0, 0.6, 1.0) * fresnel * 0.15;

    gl_FragColor = vec4(finalColor, 1.0);
  }
`

export function createFurnaceScene(container) {
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0x0a0e27)
  scene.fog = new THREE.Fog(0x0a0e27, 20, 60)

  const camera = new THREE.PerspectiveCamera(
    45,
    container.clientWidth / container.clientHeight,
    0.1,
    500
  )
  camera.position.set(18, 10, 22)

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  container.appendChild(renderer.domElement)

  const controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 8
  controls.maxDistance = 50
  controls.maxPolarAngle = Math.PI * 0.85
  controls.autoRotate = true
  controls.autoRotateSpeed = 0.3

  const ambientLight = new THREE.AmbientLight(0x404060, 0.6)
  scene.add(ambientLight)

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
  dirLight.position.set(10, 20, 15)
  scene.add(dirLight)

  const pointLight = new THREE.PointLight(0xff6633, 0.8, 50)
  pointLight.position.set(0, 5, 0)
  scene.add(pointLight)

  const bottomLight = new THREE.PointLight(0xff4400, 1.2, 40)
  bottomLight.position.set(0, -12, 0)
  scene.add(bottomLight)

  const FURNACE_HEIGHT = 24
  const RADIUS_TOP = 5.5
  const RADIUS_BOTTOM = 8.5
  const RADIAL_SEGMENTS = 72
  const HEIGHT_SEGMENTS = 32
  const EROSION_INTENSITY = 2.8

  const geometry = new THREE.CylinderGeometry(
    RADIUS_TOP,
    RADIUS_BOTTOM,
    FURNACE_HEIGHT,
    RADIAL_SEGMENTS,
    HEIGHT_SEGMENTS
  )

  const erosionCanvas = document.createElement('canvas')
  erosionCanvas.width = 256
  erosionCanvas.height = 128
  const erosionCtx = erosionCanvas.getContext('2d')

  const erosionTexture = new THREE.CanvasTexture(erosionCanvas)
  erosionTexture.wrapS = THREE.RepeatWrapping
  erosionTexture.wrapT = THREE.ClampToEdgeWrapping
  erosionTexture.magFilter = THREE.LinearFilter
  erosionTexture.minFilter = THREE.LinearFilter

  const uniforms = {
    uTime: { value: 0 },
    uErosionMap: { value: erosionTexture },
    uErosionIntensity: { value: EROSION_INTENSITY },
    uBaseRadiusTop: { value: RADIUS_TOP },
    uBaseRadiusBottom: { value: RADIUS_BOTTOM },
    uHeight: { value: FURNACE_HEIGHT },
    uLightPos: { value: new THREE.Vector3(10, 15, 15) },
  }

  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    side: THREE.DoubleSide,
  })

  const furnace = new THREE.Mesh(geometry, material)
  furnace.rotation.y = Math.PI * 0.25
  scene.add(furnace)

  const wireframeMaterial = new THREE.MeshBasicMaterial({
    color: 0x00e5ff,
    wireframe: true,
    transparent: true,
    opacity: 0.06,
  })
  const wireframe = new THREE.Mesh(geometry.clone(), wireframeMaterial)
  furnace.add(wireframe)

  const ringGeometry = new THREE.TorusGeometry(RADIUS_BOTTOM + 0.3, 0.08, 8, 64)
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0x4fc3f7,
    transparent: true,
    opacity: 0.4,
  })
  const bottomRing = new THREE.Mesh(ringGeometry, ringMaterial)
  bottomRing.rotation.x = Math.PI / 2
  bottomRing.position.y = -FURNACE_HEIGHT / 2
  scene.add(bottomRing)

  const topRing = bottomRing.clone()
  topRing.scale.set(RADIUS_TOP / RADIUS_BOTTOM, 1, RADIUS_TOP / RADIUS_BOTTOM)
  topRing.position.y = FURNACE_HEIGHT / 2
  scene.add(topRing)

  const gridHelper = new THREE.GridHelper(40, 40, 0x1e2a5a, 0x141a3a)
  gridHelper.position.y = -FURNACE_HEIGHT / 2 - 0.5
  scene.add(gridHelper)

  const layerLabels = []
  const LAYER_NAMES = ['炉身上部', '炉身上部', '炉身中部', '炉身中部', '炉腰', '炉腰', '炉腹', '炉腹']
  for (let i = 0; i < 8; i++) {
    const yPos = FURNACE_HEIGHT / 2 - (i + 0.5) * (FURNACE_HEIGHT / 8)
    const markerGeom = new THREE.RingGeometry(RADIUS_BOTTOM + 0.6, RADIUS_BOTTOM + 0.9, 64)
    const markerMat = new THREE.MeshBasicMaterial({
      color: i >= 5 ? 0xff6633 : 0x4fc3f7,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.3,
    })
    const marker = new THREE.Mesh(markerGeom, markerMat)
    marker.rotation.x = Math.PI / 2
    marker.position.y = yPos
    scene.add(marker)
    layerLabels.push({ y: yPos, name: LAYER_NAMES[i] + ` L${i}` })
  }

  let clock = new THREE.Clock()
  let animationId = null
  let running = true

  function animate() {
    if (!running) return
    animationId = requestAnimationFrame(animate)
    uniforms.uTime.value = clock.getElapsedTime()
    controls.update()
    renderer.render(scene, camera)
  }
  animate()

  function updateErosionMap(thicknessMap) {
    const w = erosionCanvas.width
    const h = erosionCanvas.height
    const imgData = erosionCtx.createImageData(w, h)
    const data = imgData.data

    const numLayers = thicknessMap.length
    const numAngles = thicknessMap[0]?.length || 36

    const originalThickness = 450

    for (let y = 0; y < h; y++) {
      const layerIdx = Math.floor((y / h) * numLayers)
      const clampedLayer = Math.min(Math.max(layerIdx, 0), numLayers - 1)
      const layerData = thicknessMap[clampedLayer] || []

      for (let x = 0; x < w; x++) {
        const angleIdx = Math.floor((x / w) * numAngles)
        const clampedAngle = Math.min(Math.max(angleIdx, 0), numAngles - 1)
        const thickness = layerData[clampedAngle] || originalThickness

        const erosionRatio = Math.max(0, Math.min(1, 1 - thickness / originalThickness))

        const idx = (y * w + x) * 4
        data[idx] = Math.floor(erosionRatio * 255)
        data[idx + 1] = 0
        data[idx + 2] = 0
        data[idx + 3] = 255
      }
    }

    erosionCtx.putImageData(imgData, 0, 0)
    erosionTexture.needsUpdate = true
  }

  function resize() {
    if (!container) return
    camera.aspect = container.clientWidth / container.clientHeight
    camera.updateProjectionMatrix()
    renderer.setSize(container.clientWidth, container.clientHeight)
  }

  window.addEventListener('resize', resize)

  function destroy() {
    running = false
    if (animationId) cancelAnimationFrame(animationId)
    window.removeEventListener('resize', resize)
    controls.dispose()
    geometry.dispose()
    material.dispose()
    erosionTexture.dispose()
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }

  return {
    scene,
    camera,
    renderer,
    furnace,
    updateErosionMap,
    resize,
    destroy,
    controls,
  }
}
