<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';

const canvasRef = ref<HTMLCanvasElement | null>(null);
let stopWater = () => {};

const BARRELS = 7;

const VERT = `#version 300 es
in vec2 position;
void main() {
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const FRAG = `#version 300 es
precision highp float;

uniform vec2 resolution;
uniform float time;
uniform float tanHalf;
uniform vec3 camPos;
uniform vec3 camFwd;
uniform vec3 camRight;
uniform vec3 camUp;
uniform vec4 barrelPos[7];
uniform mat3 barrelRot[7];
uniform vec4 ripple[8];
uniform float rippleOn;

out vec4 fragColor;

float swell(vec2 w) {
  float a = sin(dot(w, vec2(0.46, 0.18)) * 0.82 + time * 0.95);
  float b = sin(dot(w, vec2(-0.16, 0.52)) * 1.08 - time * 0.58);
  float c = sin(dot(w, vec2(0.74, 0.06)) * 1.55 + time * 1.2);
  return a * 0.26 + b * 0.13 + c * 0.05;
}

vec2 swellGrad(vec2 w) {
  float p0 = dot(w, vec2(0.46, 0.18)) * 0.82 + time * 0.95;
  float p1 = dot(w, vec2(-0.16, 0.52)) * 1.08 - time * 0.58;
  float p2 = dot(w, vec2(0.74, 0.06)) * 1.55 + time * 1.2;
  vec2 g = cos(p0) * 0.26 * vec2(0.46, 0.18) * 0.82;
  g += cos(p1) * 0.13 * vec2(-0.16, 0.52) * 1.08;
  g += cos(p2) * 0.05 * vec2(0.74, 0.06) * 1.55;
  return g;
}

float rippleHeight(vec2 w) {
  if (rippleOn < 0.5) return 0.0;
  float h = 0.0;
  for (int i = 0; i < 8; i++) {
    float amp = ripple[i].w;
    if (abs(amp) < 0.001) continue;
    float age = time - ripple[i].z;
    if (age < 0.0 || age > 1.7) continue;
    vec2 d = w - ripple[i].xy;
    float ang = atan(d.y, d.x);
    float wobble = 1.0
      + 0.07 * sin(ang * 2.0 + ripple[i].z)
      + 0.04 * sin(ang * 4.0 - age * 1.6);
    float radius = length(d);
    float expand = (0.08 + age * 4.2) * wobble;
    float width = 0.28 + age * 0.38;
    float phase = (radius - expand) / width;
    float fade = exp(-age * 1.35);
    h += amp * fade * exp(-phase * phase) * sin(phase * 2.15);
  }
  if (abs(h) < 0.0008) return 0.0;
  float kink = 0.0;
  for (int b = 0; b < 7; b++) {
    vec2 d = w - barrelPos[b].xz;
    float dist = length(d);
    float span = (dist - 0.5) / 0.24;
    float rim = exp(-span * span);
    kink += rim * sin(atan(d.y, d.x) * 2.0 + barrelPos[b].x * 4.0);
  }
  return h * (1.0 + kink * 0.28);
}

float sdBarrel(vec3 q) {
  float halfL = 0.48;
  float k = clamp(q.x / halfL, -1.0, 1.0);
  float radius = 0.34 * (1.0 - 0.22 * k * k);
  vec2 d = vec2(length(q.yz) - radius, abs(q.x) - halfL);
  return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0);
}

vec2 traceBarrels(vec3 ro, vec3 rd) {
  float best = 1e5;
  float id = -1.0;
  for (int i = 0; i < 7; i++) {
    vec3 center = barrelPos[i].xyz;
    float rad = barrelPos[i].w;
    vec3 oc = ro - center;
    float b = dot(oc, rd);
    float disc = b * b - (dot(oc, oc) - rad * rad);
    if (disc < 0.0) continue;
    float span = sqrt(disc);
    float tFar = -b + span;
    float tNear = -b - span;
    if (tFar < 0.02 || tNear > best) continue;
    float tt = max(tNear, 0.02);
    bool hit = false;
    for (int step = 0; step < 8; step++) {
      vec3 q = transpose(barrelRot[i]) * (ro + rd * tt - center);
      float dist = sdBarrel(q);
      if (dist < 0.0045) {
        hit = true;
        break;
      }
      tt += max(dist * 0.8, 0.0035);
      if (tt > tFar) break;
    }
    if (hit && tt < best) {
      best = tt;
      id = float(i);
    }
  }
  return vec2(best, id);
}

float traceWater(vec3 ro, vec3 rd) {
  if (rd.y > -0.02) return 1e5;
  float t = -ro.y / rd.y;
  for (int i = 0; i < 3; i++) {
    float h = swell((ro + rd * t).xz);
    t = (h - ro.y) / rd.y;
    if (t < 0.0) return 1e5;
  }
  return t;
}

float hairline(float d) {
  float fw = max(fwidth(d), 1e-4);
  return 1.0 - smoothstep(fw * 0.2, fw * 1.05, abs(d));
}

float engrave(float coord) {
  float px = max(fwidth(coord), 1e-3);
  float fw = min(px * 0.7, 0.22);
  float dist = abs(fract(coord) - 0.5);
  return smoothstep(0.5 - fw, 0.5 - fw * 0.2, dist);
}

float hatch(float coord, float width) {
  float fw = min(fwidth(coord) * 1.15, 0.1);
  float dist = abs(fract(coord) - 0.5);
  return smoothstep(0.5 - width - fw, 0.5 - width + fw, dist);
}

vec3 barrelInk(vec3 p, float id, vec3 rd) {
  int index = int(id + 0.5);
  vec3 q = transpose(barrelRot[index]) * (p - barrelPos[index].xyz);
  vec3 nLocal = normalize(vec3(
    sdBarrel(q + vec3(0.01, 0.0, 0.0)) - sdBarrel(q - vec3(0.01, 0.0, 0.0)),
    sdBarrel(q + vec3(0.0, 0.01, 0.0)) - sdBarrel(q - vec3(0.0, 0.01, 0.0)),
    sdBarrel(q + vec3(0.0, 0.0, 0.01)) - sdBarrel(q - vec3(0.0, 0.0, 0.01))
  ));
  vec3 n = barrelRot[index] * nLocal;
  float angle = atan(q.z, q.y);
  float side = smoothstep(0.9, 0.48, abs(nLocal.x));
  float staves = engrave(angle * 40.0 / 6.2831853) * side;
  float hoops = max(
    max(hairline(q.x + 0.34), hairline(q.x - 0.34)),
    max(hairline(q.x + 0.12), hairline(q.x - 0.12))
  ) * side;
  float endR = 0.34 * 0.78;
  float radial = length(q.yz);
  float capFace = smoothstep(0.34, 0.72, abs(nLocal.x));
  float boards = engrave(q.y * 30.0);
  boards *= smoothstep(endR + 0.012, endR - 0.02, radial);
  float capRim = hairline(radial - endR);
  float cap = max(boards, capRim) * capFace;
  float facing = clamp(dot(n, -rd), 0.0, 1.0);
  float ink = max(max(staves, hoops), cap);
  return vec3(ink, facing, 0.0);
}

void main() {
  vec2 ndc = gl_FragCoord.xy / resolution * 2.0 - 1.0;
  float aspect = resolution.x / resolution.y;
  vec3 rd = normalize(camFwd + camRight * ndc.x * tanHalf * aspect + camUp * ndc.y * tanHalf);
  vec3 ro = camPos;

  vec3 paper = vec3(0.993, 0.994, 0.993);
  vec3 ink = vec3(0.035, 0.035, 0.037);
  vec3 lane = vec3(0.50, 0.51, 0.74);
  vec3 deep = vec3(0.42, 0.44, 0.68);
  vec3 color = paper;

  vec2 barrel = traceBarrels(ro, rd);
  float tw = traceWater(ro, rd);
  vec3 barrelPoint = ro + rd * barrel.x;
  float underWater = swell(barrelPoint.xz) - barrelPoint.y;
  bool showBarrel = barrel.x < tw || (barrel.x < 40.0 && underWater < 0.05);

  if (showBarrel) {
    vec3 p = barrelPoint;
    vec3 mark = barrelInk(p, barrel.y, rd);
    color = mix(paper, ink, clamp(mark.x, 0.0, 1.0));
  } else if (tw < 40.0) {
    vec3 p = ro + rd * tw;
    float rip = rippleHeight(p.xz);
    if (abs(rip) > 0.001) {
      tw = (swell(p.xz) + rip - ro.y) / rd.y;
      p = ro + rd * tw;
      rip = rippleHeight(p.xz);
    }
    float h = swell(p.xz) + rip;
    float laneCoord = p.z * 3.35 + h * 3.1;
    float lines = hatch(laneCoord, 0.016);
    float dashPhase = p.x * 0.38 + floor(laneCoord + 0.5) * 0.37;
    float dashWidth = max(fwidth(dashPhase) * 1.4, 0.01);
    float dashU = fract(dashPhase);
    float dash = smoothstep(0.0, dashWidth, dashU) * (1.0 - smoothstep(0.88, 0.88 + dashWidth, dashU));
    dash = mix(dash, 1.0, smoothstep(0.05, 0.2, abs(rip)));
    lines *= dash;
    vec2 g = swellGrad(p.xz);
    if (abs(rip) > 0.002) {
      float e = 0.16;
      g.x += (rippleHeight(p.xz + vec2(e, 0.0)) - rippleHeight(p.xz - vec2(e, 0.0))) / (e * 2.0);
      g.y += (rippleHeight(p.xz + vec2(0.0, e)) - rippleHeight(p.xz - vec2(0.0, e))) / (e * 2.0);
    }
    vec3 n = normalize(vec3(-g.x, 1.0, -g.y));
    float shade = clamp(0.96 + dot(n, normalize(vec3(-0.2, 0.85, 0.2))) * 0.05, 0.0, 1.0);
    color = mix(paper, lane, lines) * shade;

    vec3 rdR = reflect(rd, n);
    vec3 roR = p + n * 0.03;
    vec2 rh = traceBarrels(roR, rdR);
    if (rh.x < 3.4) {
      vec3 rp = roR + rdR * rh.x;
      vec3 mark = barrelInk(rp, rh.y, rdR);
      color = mix(color, deep, clamp(mark.x, 0.0, 1.0) * 0.58 * exp(-rh.x * 0.36));
    }
  }

  fragColor = vec4(color, 1.0);
}
`;

type Barrel = {
  x: number;
  z: number;
  vx: number;
  vz: number;
  yaw: number;
  spin: number;
  pitch: number;
  roll: number;
  pitchV: number;
  rollV: number;
  hop: number;
};

function barrelMatrix(yaw: number, pitch: number, roll: number) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const cr = Math.cos(roll);
  const sr = Math.sin(roll);
  const xAxis = [cy * cp, sp, sy * cp];
  const yAxis = [cy * (-sp * cr) - sy * sr, cp * cr, sy * (-sp * cr) + cy * sr];
  const zAxis = [cy * (sp * sr) - sy * cr, -cp * sr, sy * (sp * sr) + cy * cr];
  return new Float32Array([
    xAxis[0], xAxis[1], xAxis[2],
    yAxis[0], yAxis[1], yAxis[2],
    zAxis[0], zAxis[1], zAxis[2],
  ]);
}

function swell(x: number, z: number, time: number) {
  const a = Math.sin((x * 0.46 + z * 0.18) * 0.82 + time * 0.95);
  const b = Math.sin((x * -0.16 + z * 0.52) * 1.08 - time * 0.58);
  const c = Math.sin((x * 0.74 + z * 0.06) * 1.55 + time * 1.2);
  return a * 0.26 + b * 0.13 + c * 0.05;
}

function rippleHeight(
  x: number,
  z: number,
  time: number,
  ripples: { x: number; z: number; birth: number; amp: number }[],
  barrels: { x: number; z: number }[],
) {
  let h = 0;
  for (const ripple of ripples) {
    if (Math.abs(ripple.amp) < 0.001) continue;
    const age = time - ripple.birth;
    if (age < 0 || age > 1.7) continue;
    const dx = x - ripple.x;
    const dz = z - ripple.z;
    const ang = Math.atan2(dz, dx);
    const wobble = 1
      + 0.07 * Math.sin(ang * 2 + ripple.birth)
      + 0.04 * Math.sin(ang * 4 - age * 1.6);
    const radius = Math.hypot(dx, dz);
    const expand = (0.08 + age * 4.2) * wobble;
    const width = 0.28 + age * 0.38;
    const phase = (radius - expand) / width;
    const fade = Math.exp(-age * 1.35);
    h += ripple.amp * fade * Math.exp(-phase * phase) * Math.sin(phase * 2.15);
  }
  let kink = 0;
  for (const barrel of barrels) {
    const dx = x - barrel.x;
    const dz = z - barrel.z;
    const dist = Math.hypot(dx, dz);
    const rimSpan = (dist - 0.5) / 0.24;
    const rim = Math.exp(-(rimSpan * rimSpan));
    kink += rim * Math.sin(Math.atan2(dz, dx) * 2 + barrel.x * 4);
  }
  return h * (1 + kink * 0.28);
}

onMounted(() => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, powerPreference: 'high-performance' });
  if (!gl) return;

  const compile = (type: number, source: string) => {
    const shader = gl.createShader(type);
    if (!shader) throw new Error('shader');
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(shader) ?? '';
      gl.deleteShader(shader);
      throw new Error(log);
    }
    return shader;
  };

  let program: WebGLProgram;
  try {
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, FRAG);
    program = gl.createProgram()!;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.bindAttribLocation(program, 0, 'position');
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) ?? 'link failed');
    }
  } catch (error) {
    console.error(error);
    return;
  }

  gl.useProgram(program);
  gl.bindVertexArray(gl.createVertexArray());
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  const loc = (name: string) => gl.getUniformLocation(program, name);
  const resolutionLoc = loc('resolution');
  const timeLoc = loc('time');
  const tanLoc = loc('tanHalf');
  const camPosLoc = loc('camPos');
  const camFwdLoc = loc('camFwd');
  const camRightLoc = loc('camRight');
  const camUpLoc = loc('camUp');
  const posLoc = Array.from({ length: BARRELS }, (_, i) => loc(`barrelPos[${i}]`));
  const rotLoc = Array.from({ length: BARRELS }, (_, i) => loc(`barrelRot[${i}]`));
  const rippleLoc = Array.from({ length: 8 }, (_, i) => loc(`ripple[${i}]`));
  const rippleOnLoc = loc('rippleOn');

  const camPos = [0, 5.2, -0.8];
  const target = [0, 0.1, 9];
  const sub = (a: number[], b: number[]) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const norm = (v: number[]) => {
    const l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  };
  const cross = (a: number[], b: number[]) => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
  const camFwd = norm(sub(target, camPos));
  const camRight = norm(cross(camFwd, [0, 1, 0]));
  const camUp = cross(camRight, camFwd);
  const tanHalf = Math.tan((48 * Math.PI) / 360);

  gl.uniform3f(camPosLoc, camPos[0], camPos[1], camPos[2]);
  gl.uniform3f(camFwdLoc, camFwd[0], camFwd[1], camFwd[2]);
  gl.uniform3f(camRightLoc, camRight[0], camRight[1], camRight[2]);
  gl.uniform3f(camUpLoc, camUp[0], camUp[1], camUp[2]);
  gl.uniform1f(tanLoc, tanHalf);
  gl.uniform1f(rippleOnLoc, 0);

  const barrels: Barrel[] = [
    { x: -4.8, z: 12.6, vx: 0.04, vz: 0.01, yaw: 0.45, spin: 0.05 },
    { x: -1.6, z: 13.2, vx: -0.03, vz: 0.01, yaw: 1.35, spin: -0.04 },
    { x: 2.8, z: 12.5, vx: 0.03, vz: -0.01, yaw: -0.55, spin: 0.05 },
    { x: -3.6, z: 4.15, vx: 0.05, vz: -0.01, yaw: 0.7, spin: 0.08 },
    { x: -2.2, z: 4.9, vx: -0.04, vz: 0.01, yaw: 2.05, spin: -0.06 },
    { x: 3.0, z: 4.05, vx: 0.04, vz: 0.02, yaw: -0.35, spin: 0.07 },
    { x: 4.5, z: 4.7, vx: -0.04, vz: -0.01, yaw: 0.95, spin: 0.06 },
  ].map((barrel) => ({ ...barrel, pitch: 0, roll: 0, pitchV: 0, rollV: 0, hop: 0 }));

  let viewW = 1;
  let viewH = 1;
  let raf = 0;
  let running = true;
  const start = performance.now();
  let last = start;
  const pointer: { x: number; y: number; down: boolean; barrel: Barrel | null } = {
    x: 0,
    y: 0,
    down: false,
    barrel: null,
  };
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const resize = () => {
    const rect = canvas.getBoundingClientRect();
    viewW = Math.max(1, rect.width);
    viewH = Math.max(1, rect.height);
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    let w = Math.floor(viewW * dpr);
    let h = Math.floor(viewH * dpr);
    const budget = 2000 * 1250;
    if (w * h > budget) {
      const scale = Math.sqrt(budget / (w * h));
      w = Math.max(1, Math.floor(w * scale));
      h = Math.max(1, Math.floor(h * scale));
    }
    canvas.width = w;
    canvas.height = h;
    gl.viewport(0, 0, w, h);
    gl.uniform2f(resolutionLoc, w, h);
  };

  const ripples = Array.from({ length: 8 }, () => ({ x: 0, z: 0, birth: -10, amp: 0 }));
  let rippleSlot = 0;
  let lastRippleAt = -10;
  let simTime = 0;
  const spawnRipple = (x: number, z: number, amp: number) => {
    const slot = ripples[rippleSlot];
    rippleSlot = (rippleSlot + 1) % ripples.length;
    slot.x = x;
    slot.z = z;
    slot.birth = simTime;
    slot.amp = amp;
    lastRippleAt = simTime;
  };

  const surface = (x: number, z: number, time: number) => swell(x, z, time) + rippleHeight(x, z, time, ripples, barrels);
  const floatY = (barrel: Barrel, time: number) => {
    const ax = Math.cos(barrel.yaw);
    const az = Math.sin(barrel.yaw);
    const endDrop = 0.48 * Math.sin(Math.abs(barrel.pitch)) + 0.27 * Math.cos(barrel.pitch);
    const bellyDrop = 0.34 * Math.cos(barrel.roll);
    const drop = Math.max(endDrop, bellyDrop);
    let water = surface(barrel.x, barrel.z, time);
    const probes = [
      [ax * 0.48, az * 0.48],
      [-ax * 0.48, -az * 0.48],
      [-az * 0.34, ax * 0.34],
      [az * 0.34, -ax * 0.34],
    ];
    for (const [dx, dz] of probes) {
      water = Math.max(water, surface(barrel.x + dx, barrel.z + dz, time));
    }
    return water + drop + 0.03 + barrel.hop;
  };

  const ray = (px: number, py: number) => {
    const ndcX = (px / viewW) * 2 - 1;
    const ndcY = 1 - (py / viewH) * 2;
    const aspect = viewW / viewH;
    const rd = [
      camFwd[0] + camRight[0] * ndcX * tanHalf * aspect + camUp[0] * ndcY * tanHalf,
      camFwd[1] + camRight[1] * ndcX * tanHalf * aspect + camUp[1] * ndcY * tanHalf,
      camFwd[2] + camRight[2] * ndcX * tanHalf * aspect + camUp[2] * ndcY * tanHalf,
    ];
    return norm(rd);
  };

  const hitPlane = (rd: number[]) => {
    if (Math.abs(rd[1]) < 1e-4) return null;
    const t = -camPos[1] / rd[1];
    if (t < 0) return null;
    return [camPos[0] + rd[0] * t, camPos[2] + rd[2] * t];
  };

  const pushBarrels = (x: number, z: number, mx: number, mz: number) => {
    for (const barrel of barrels) {
      const dx = barrel.x - x;
      const dz = barrel.z - z;
      const dist = Math.hypot(dx, dz) || 0.0001;
      if (dist > 1.55) continue;
      const force = 1 - dist / 1.55;
      barrel.vx += (mx * 1.15 + (dx / dist) * 0.4) * force;
      barrel.vz += (mz * 1.15 + (dz / dist) * 0.4) * force;
      barrel.spin += mx * 0.7 * force;
    }
  };

  const stepBarrels = (dt: number, time: number) => {
    for (const barrel of barrels) {
      const slopeX = surface(barrel.x + 0.2, barrel.z, time) - surface(barrel.x - 0.2, barrel.z, time);
      const slopeZ = surface(barrel.x, barrel.z + 0.2, time) - surface(barrel.x, barrel.z - 0.2, time);
      const ax = Math.cos(barrel.yaw);
      const az = Math.sin(barrel.yaw);
      const along = slopeX * ax + slopeZ * az;
      const side = -slopeX * az + slopeZ * ax;
      barrel.vx += -slopeX * 3.4 * dt;
      barrel.vz += -slopeZ * 3.4 * dt;
      barrel.pitchV += (Math.atan(along) - barrel.pitch) * 11 * dt;
      barrel.rollV += (Math.atan(side) * 0.75 - barrel.roll) * 11 * dt;
      barrel.pitchV *= Math.exp(-5.5 * dt);
      barrel.rollV *= Math.exp(-5.5 * dt);
      barrel.pitch += barrel.pitchV * dt;
      barrel.roll += barrel.rollV * dt;
      const tiltLimit = 0.24;
      if (barrel.pitch > tiltLimit) {
        barrel.pitch = tiltLimit;
        barrel.pitchV = Math.min(barrel.pitchV, 0);
      } else if (barrel.pitch < -tiltLimit) {
        barrel.pitch = -tiltLimit;
        barrel.pitchV = Math.max(barrel.pitchV, 0);
      }
      if (barrel.roll > tiltLimit) {
        barrel.roll = tiltLimit;
        barrel.rollV = Math.min(barrel.rollV, 0);
      } else if (barrel.roll < -tiltLimit) {
        barrel.roll = -tiltLimit;
        barrel.rollV = Math.max(barrel.rollV, 0);
      }
      barrel.spin += side * 6 * dt;
      barrel.hop *= Math.exp(-4.2 * dt);
      barrel.vx *= 0.985;
      barrel.vz *= 0.985;
      barrel.spin *= 0.99;
      barrel.x += barrel.vx * dt;
      barrel.z += barrel.vz * dt;
      barrel.yaw += barrel.spin * dt;
    }
    for (let i = 0; i < barrels.length; i += 1) {
      for (let j = i + 1; j < barrels.length; j += 1) {
        const a = barrels[i];
        const b = barrels[j];
        const dx = b.x - a.x;
        const dz = b.z - a.z;
        const dist = Math.hypot(dx, dz) || 0.0001;
        const min = 0.95;
        if (dist >= min) continue;
        const overlap = (min - dist) * 0.5;
        const ux = dx / dist;
        const uz = dz / dist;
        a.x -= ux * overlap;
        a.z -= uz * overlap;
        b.x += ux * overlap;
        b.z += uz * overlap;
        const av = a.vx * ux + a.vz * uz;
        const bv = b.vx * ux + b.vz * uz;
        a.vx += (bv - av) * ux * 0.85;
        a.vz += (bv - av) * uz * 0.85;
        b.vx += (av - bv) * ux * 0.85;
        b.vz += (av - bv) * uz * 0.85;
      }
    }
    for (const barrel of barrels) {
      if (barrel.x < -5.2) {
        barrel.x = -5.2;
        barrel.vx = Math.abs(barrel.vx);
      } else if (barrel.x > 5.2) {
        barrel.x = 5.2;
        barrel.vx = -Math.abs(barrel.vx);
      }
      if (barrel.z < 2.4) {
        barrel.z = 2.4;
        barrel.vz = Math.abs(barrel.vz);
      } else if (barrel.z > 13.4) {
        barrel.z = 13.4;
        barrel.vz = -Math.abs(barrel.vz);
      }
    }
  };

  const frame = (ts: number) => {
    const dt = Math.min(0.033, (ts - last) / 1000) || 0.016;
    last = ts;
    const time = (ts - start) / 1000;
    simTime = time;
    if (!reduced) stepBarrels(dt, time);
    gl.uniform1f(timeLoc, time);
    let rippleOn = 0;
    for (let i = 0; i < ripples.length; i += 1) {
      const age = time - ripples[i].birth;
      if (Math.abs(ripples[i].amp) > 0.001 && age >= 0 && age < 1.7) rippleOn = 1;
    }
    gl.uniform1f(rippleOnLoc, rippleOn);
    for (let i = 0; i < barrels.length; i += 1) {
      const barrel = barrels[i];
      const y = floatY(barrel, time);
      gl.uniform4f(posLoc[i], barrel.x, y, barrel.z, 0.78);
      gl.uniformMatrix3fv(rotLoc[i], false, barrelMatrix(barrel.yaw, barrel.pitch, barrel.roll));
    }
    for (let i = 0; i < ripples.length; i += 1) {
      const ripple = ripples[i];
      gl.uniform4f(rippleLoc[i], ripple.x, ripple.z, ripple.birth, ripple.amp);
    }
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (running && !reduced) raf = requestAnimationFrame(frame);
  };

  const local = (event: PointerEvent) => {
    const rect = canvas.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const pickBarrel = (rd: number[]) => {
    let best: Barrel | null = null;
    let bestT = 1e9;
    for (const barrel of barrels) {
      const cy = floatY(barrel, simTime);
      const oc = [camPos[0] - barrel.x, camPos[1] - cy, camPos[2] - barrel.z];
      const b = oc[0] * rd[0] + oc[1] * rd[1] + oc[2] * rd[2];
      const c = oc[0] * oc[0] + oc[1] * oc[1] + oc[2] * oc[2] - 0.62 * 0.62;
      const disc = b * b - c;
      if (disc < 0) continue;
      const t = -b - Math.sqrt(disc);
      if (t > 0.05 && t < bestT) {
        bestT = t;
        best = barrel;
      }
    }
    return best;
  };

  const kickBarrel = (barrel: Barrel, hit: number[] | null) => {
    const dx = hit ? barrel.x - hit[0] : 0;
    const dz = hit ? barrel.z - hit[1] : 0;
    const ax = Math.cos(barrel.yaw);
    const az = Math.sin(barrel.yaw);
    const along = dx * ax + dz * az;
    const side = -dx * az + dz * ax;
    const sideSign = side === 0 ? 1 : Math.sign(side);
    barrel.spin += side * 1.1 + sideSign * 0.35;
    barrel.pitchV += along * 1.3 + 0.28;
    barrel.rollV += side * 1.05;
    barrel.vx += dx * 0.28;
    barrel.vz += dz * 0.28;
    barrel.hop = 0.045;
  };

  const onDown = (event: PointerEvent) => {
    if (reduced) return;
    pointer.down = true;
    const point = local(event);
    pointer.x = point.x;
    pointer.y = point.y;
    const rd = ray(point.x, point.y);
    const barrel = pickBarrel(rd);
    const hit = hitPlane(rd);
    pointer.barrel = barrel;
    if (barrel) {
      kickBarrel(barrel, hit);
      canvas.setPointerCapture(event.pointerId);
      return;
    }
    if (!hit) return;
    spawnRipple(hit[0], hit[1], -0.48);
    pushBarrels(hit[0], hit[1], 0, 0);
    canvas.setPointerCapture(event.pointerId);
  };

  const onMove = (event: PointerEvent) => {
    if (reduced || !pointer.down) return;
    const point = local(event);
    const rd = ray(point.x, point.y);
    const hit = hitPlane(rd);
    const prev = hitPlane(ray(pointer.x, pointer.y));
    if (pointer.barrel && hit && prev) {
      pointer.barrel.x += hit[0] - prev[0];
      pointer.barrel.z += hit[1] - prev[1];
      pointer.barrel.spin += (hit[0] - prev[0]) * 1.6;
      pointer.barrel.yaw += (hit[1] - prev[1]) * 0.35;
    } else if (!pointer.barrel && hit) {
      const moved = prev ? Math.hypot(hit[0] - prev[0], hit[1] - prev[1]) : 0;
      if (simTime - lastRippleAt > 0.28 || moved > 1.15) spawnRipple(hit[0], hit[1], -0.32);
      if (prev) pushBarrels(hit[0], hit[1], hit[0] - prev[0], hit[1] - prev[1]);
    }
    pointer.x = point.x;
    pointer.y = point.y;
  };

  const onUp = () => {
    pointer.down = false;
    pointer.barrel = null;
  };

  resize();
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerup', onUp);
  canvas.addEventListener('pointercancel', onUp);
  const observer = new ResizeObserver(resize);
  observer.observe(canvas);
  raf = requestAnimationFrame(frame);

  stopWater = () => {
    running = false;
    cancelAnimationFrame(raf);
    observer.disconnect();
    canvas.removeEventListener('pointerdown', onDown);
    canvas.removeEventListener('pointermove', onMove);
    canvas.removeEventListener('pointerup', onUp);
    canvas.removeEventListener('pointercancel', onUp);
  };
});

onUnmounted(() => {
  stopWater();
});
</script>

<template>
  <canvas ref="canvasRef" class="water-field" aria-hidden="true"></canvas>
</template>

<style scoped>
.water-field {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  touch-action: none;
  background: #f6f7fb;
}
</style>
