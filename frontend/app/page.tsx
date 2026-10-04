import AgenticFactory3D from "@/components/ui/agentic-factory-3d";
import { AnimatedCardChart } from "@/components/ui/animated-card-chart";

export default function Demo() {
  return (
    <div className="w-full min-h-screen bg-black overflow-x-hidden text-white font-sans selection:bg-amber-500/30">
      <AgenticFactory3D />
      
      <section id="capabilities" className="py-24 px-6 md:px-12 max-w-7xl mx-auto border-t border-white/5">
        <div className="mb-12">
          <div className="h-0.5 w-12 bg-red-600 mb-4"></div>
          <h2 className="text-4xl font-serif tracking-tight">Core Capabilities</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <AnimatedCardChart 
            className="md:col-span-2 min-h-[350px]"
            title="Automated Data Cleaning"
            description="No more manual wrangling. Our AI agents automatically detect anomalies, fill missing values, and normalize schemas across all your unstructured sources."
            tagTitle="Automated Pipeline"
            tagDescription="Optimizing 10M+ records seamlessly."
            chartData={[40, 60, 45, 75, 40, 85, 50, 95]}
            colorTheme="amber"
          />
          
          <AnimatedCardChart 
            className="min-h-[350px]"
            title="Insight Engine"
            description="Query your data using natural language. Get executive summaries, trend analysis, and deep-dives instantly."
            tagTitle="Generative BI"
            tagDescription="Narratives built for executives."
            chartData={[30, 60, 20, 80, 40, 70]}
            colorTheme="blue"
          />

          <AnimatedCardChart 
            className="min-h-[350px]"
            title="Real-Time Streaming"
            description="Connect to Kafka, Kinesis, or WebSockets. Process and visualize data streams with millisecond latency."
            tagTitle="99.9% Uptime"
            tagDescription="Live telemetry and dashboards."
            chartData={[50, 20, 90, 40, 75, 55]}
            colorTheme="emerald"
          />
        </div>
      </section>
    </div>
  );
}
