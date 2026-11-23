'use client';

// Vendored from React Bits (https://github.com/DavidHDev/react-bits), src/ts-default/Animations/AnimatedContent/AnimatedContent.tsx
// at commit 701a8acc34f7 on 2026-11-21. MIT + Commons Clause, see LICENSE.md.
// Local adaptations:
//  - GSAP + ScrollTrigger replaced by the Web Animations API and IntersectionObserver: no extra npm dependency.
//  - Kept props: distance, direction, reverse, duration, ease, initialOpacity, animateOpacity, scale, blur,
//    threshold, delay, trigger ('scroll' | 'mount'), once, onStart, onComplete. GSAP-only extras
//    (scrub, wipe, stagger, rotate, tilt, disappear*) are not ported.
//  - Named GSAP eases map to CSS cubic-bezier curves; any CSS easing string is also accepted.
//  - Reduced motion comes from ../use-reduced-motion (content shows immediately, no transform).

import { useEffect, useLayoutEffect, useRef, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';
import { useReducedMotion } from '../use-reduced-motion';

export interface AnimatedContentProps extends Omit<HTMLAttributes<HTMLDivElement>, 'onAnimationStart'> {
  children?: ReactNode;
  distance?: number;
  direction?: 'vertical' | 'horizontal';
  reverse?: boolean;
  duration?: number;
  ease?: string;
  initialOpacity?: number;
  animateOpacity?: boolean;
  scale?: number;
  blur?: number;
  threshold?: number;
  delay?: number;
  trigger?: 'scroll' | 'mount';
  once?: boolean;
  onStart?: () => void;
  onComplete?: () => void;
  className?: string;
  style?: CSSProperties;
}

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

const EASES: Record<string, string> = {
  none: 'linear',
  'power1.out': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  'power2.out': 'cubic-bezier(0.215, 0.61, 0.355, 1)',
  'power3.out': 'cubic-bezier(0.165, 0.84, 0.44, 1)',
  'power4.out': 'cubic-bezier(0.23, 1, 0.32, 1)',
  'expo.out': 'cubic-bezier(0.19, 1, 0.22, 1)'
};

const AnimatedContent = ({
  children,
  distance = 100,
  direction = 'vertical',
  reverse = false,
  duration = 0.8,
  ease = 'power3.out',
  initialOpacity = 0,
  animateOpacity = true,
  scale = 1,
  blur = 0,
  threshold = 0.1,
  delay = 0,
  trigger = 'scroll',
  once = true,
  onStart,
  onComplete,
  className = '',
  style,
  ...props
}: AnimatedContentProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const callbacksRef = useRef({ onStart, onComplete });
  useIsomorphicLayoutEffect(() => {
    callbacksRef.current = { onStart, onComplete };
  });
  const reducedMotion = useReducedMotion();

  useIsomorphicLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    el.style.visibility = 'visible';
    if (reducedMotion || typeof el.animate !== 'function') {
      callbacksRef.current.onComplete?.();
      return undefined;
    }
    const axis = direction === 'horizontal' ? 'X' : 'Y';
    const offset = distance * (reverse ? -1 : 1);
    const from: Keyframe = {
      transform: `translate${axis}(${offset}px) scale(${scale})`,
      opacity: animateOpacity ? initialOpacity : 1,
      ...(blur > 0 ? { filter: `blur(${blur}px)` } : {})
    };
    const to: Keyframe = { transform: 'none', opacity: 1, ...(blur > 0 ? { filter: 'blur(0px)' } : {}) };
    let animation: Animation | null = null;
    const play = () => {
      callbacksRef.current.onStart?.();
      animation = el.animate([from, to], {
        duration: Math.max(0, duration) * 1000,
        delay: Math.max(0, delay) * 1000,
        easing: EASES[ease] ?? ease,
        fill: 'backwards'
      });
      animation.onfinish = () => callbacksRef.current.onComplete?.();
    };
    if (trigger === 'mount' || typeof IntersectionObserver === 'undefined') {
      play();
      return () => animation?.cancel();
    }
    el.animate([from, from], { duration: 1, fill: 'forwards' });
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.getAnimations().forEach(running => running.cancel());
          play();
          if (once) observer.disconnect();
        } else if (!once) {
          animation?.reverse();
        }
      },
      { threshold }
    );
    observer.observe(el);
    return () => {
      observer.disconnect();
      el.getAnimations().forEach(running => running.cancel());
    };
  }, [distance, direction, reverse, duration, ease, initialOpacity, animateOpacity, scale, blur, threshold, delay, trigger, once, reducedMotion]);

  return (
    <div ref={ref} className={className} style={{ visibility: 'hidden', ...style }} {...props}>
      {children}
    </div>
  );
};

export default AnimatedContent;
