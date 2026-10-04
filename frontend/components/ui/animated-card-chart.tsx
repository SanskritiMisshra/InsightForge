"use client";

import * as React from "react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface AnimatedCardChartProps {
  title: string;
  description: string;
  tagTitle: string;
  tagDescription: string;
  chartData: number[];
  colorTheme?: "amber" | "blue" | "emerald";
  className?: string;
}

export function AnimatedCardChart({
  title,
  description,
  tagTitle,
  tagDescription,
  chartData,
  colorTheme = "amber",
  className,
}: AnimatedCardChartProps) {
  const [isHovered, setIsHovered] = useState(false);

  const colors = {
    amber: {
      gradient: "from-amber-500/20 to-transparent",
      barDefault: "bg-amber-900/40",
      barHover: "bg-amber-500",
      border: "border-amber-500/20",
      text: "text-amber-500",
      bgHover: "bg-amber-950/20",
      borderHover: "border-amber-500/50",
    },
    blue: {
      gradient: "from-blue-500/20 to-transparent",
      barDefault: "bg-blue-900/40",
      barHover: "bg-blue-500",
      border: "border-blue-500/20",
      text: "text-blue-500",
      bgHover: "bg-blue-950/20",
      borderHover: "border-blue-500/50",
    },
    emerald: {
      gradient: "from-emerald-500/20 to-transparent",
      barDefault: "bg-emerald-900/40",
      barHover: "bg-emerald-500",
      border: "border-emerald-500/20",
      text: "text-emerald-500",
      bgHover: "bg-emerald-950/20",
      borderHover: "border-emerald-500/50",
    },
  };

  const theme = colors[colorTheme];

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border bg-black/40 backdrop-blur-md transition-all duration-500 flex flex-col",
        isHovered ? theme.borderHover : "border-white/10",
        isHovered ? theme.bgHover : "",
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Background Grid Pattern */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-20 transition-opacity duration-500"
        style={{
          backgroundImage: "linear-gradient(to right, #444 1px, transparent 1px), linear-gradient(to bottom, #444 1px, transparent 1px)",
          backgroundSize: "20px 20px",
          maskImage: "radial-gradient(circle at center, black, transparent 80%)",
          WebkitMaskImage: "radial-gradient(circle at center, black, transparent 80%)"
        }}
      />

      {/* Hover Radial Gradient Glow */}
      <div
        className={cn(
          "absolute left-1/2 top-1/2 h-[300px] w-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-r blur-3xl transition-opacity duration-500 pointer-events-none",
          theme.gradient,
          isHovered ? "opacity-100" : "opacity-0"
        )}
      />

      {/* Chart Section */}
      <div className="relative flex-1 p-6 flex flex-col items-center justify-center min-h-[200px]">
        
        {/* Pills / Top Info (Fades out on hover) */}
        <div className="absolute top-4 left-4 flex gap-2 transition-opacity duration-300">
          <AnimatePresence>
            {!isHovered && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex gap-2"
              >
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/50">
                  <div className={cn("h-1.5 w-1.5 rounded-full", theme.barHover)} />
                  +15.2%
                </span>
                <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-white/50">
                  <div className={cn("h-1.5 w-1.5 rounded-full", theme.barHover)} />
                  +18.7%
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* The Bars */}
        <div className="flex items-end justify-center gap-2 h-24 mt-4 w-full relative z-10">
          {chartData.map((height, i) => (
            <motion.div
              key={i}
              initial={false}
              animate={{
                height: isHovered ? `${Math.min(100, height * 1.5)}%` : `${height}%`,
                scaleY: isHovered ? 1.1 : 1,
              }}
              transition={{
                type: "spring",
                stiffness: 300,
                damping: 20,
                delay: i * 0.05,
              }}
              className={cn(
                "w-4 rounded-sm transition-colors duration-500 origin-bottom",
                isHovered ? theme.barHover : theme.barDefault
              )}
            />
          ))}
        </div>

        {/* Hover Tooltip Popup */}
        <AnimatePresence>
          {isHovered && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ type: "spring", stiffness: 400, damping: 25 }}
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] max-w-[250px] z-20"
            >
              <div className="rounded-lg border border-white/10 bg-black/60 backdrop-blur-xl p-3 shadow-2xl">
                <div className="flex items-center gap-2 mb-1">
                  <div className={cn("h-2 w-2 rounded-full", theme.barHover)} />
                  <span className="text-sm font-medium text-white">{tagTitle}</span>
                </div>
                <p className="text-xs text-white/60 font-mono">
                  {tagDescription}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

      </div>

      {/* Footer Text */}
      <div className="border-t border-white/5 bg-white/[0.02] p-6 z-10 relative">
        <h3 className="text-xl font-medium tracking-tight text-white mb-2">
          {title}
        </h3>
        <p className="text-sm text-white/50 leading-relaxed font-mono">
          {description}
        </p>
      </div>
    </div>
  );
}
