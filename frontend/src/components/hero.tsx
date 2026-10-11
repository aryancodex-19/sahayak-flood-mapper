import { motion } from "framer-motion";
import { ArrowRight, Download } from "lucide-react";

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.12 } },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" as const } },
};

const buttonMotion = {
  whileHover: { scale: 1.03 },
  whileTap: { scale: 0.97 },
  transition: { type: "spring" as const, stiffness: 400, damping: 17 },
};

interface HeroProps {
  onViewMap: () => void;
}

export function Hero({ onViewMap }: HeroProps) {
  return (
    <section className="relative -mx-6 -mt-6 min-h-screen overflow-hidden">
      <div className="absolute inset-x-[-18%] bottom-[-34%] h-[78%] rounded-[100%] blur-3xl" style={{ background: "radial-gradient(ellipse at center, rgba(56, 189, 248, 0.58) 0%, rgba(59, 130, 246, 0.34) 34%, rgba(99, 102, 241, 0.2) 58%, transparent 78%)" }} />
      <div className="absolute inset-x-0 bottom-0 h-[68%]" style={{ background: "linear-gradient(to top, rgba(37, 99, 235, 0.42), rgba(14, 165, 233, 0.2) 42%, transparent 78%)" }} />
      <div className="absolute inset-0" style={{ background: "linear-gradient(to bottom, #080B18 0%, rgba(8, 11, 24, 0.68) 38%, rgba(8, 11, 24, 0.12) 100%)" }} />

      <motion.div variants={containerVariants} initial="hidden" animate="visible" className="relative mx-auto flex min-h-[80vh] max-w-4xl flex-col items-center justify-center px-6 py-24 text-center">
        <motion.div variants={itemVariants} className="rounded-full border border-border bg-background/50 px-4 py-1.5 text-sm font-medium text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.16),0_12px_40px_rgba(0,0,0,0.08)] backdrop-blur-md">
          Kamrup, Assam — Live Monitoring
        </motion.div>
        <motion.h1 variants={itemVariants} className="mt-8 max-w-3xl text-balance text-5xl font-medium leading-[0.96] tracking-normal md:text-6xl lg:text-7xl">
          <motion.span
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          >
            Flood Damage Mapping from Space
          </motion.span>
        </motion.h1>
        <motion.p variants={itemVariants} className="mt-6 max-w-2xl text-pretty text-base leading-7 text-muted-foreground md:text-lg">
          Satellite-based rescue prioritization for cut-off settlements in Assam.
        </motion.p>
        <motion.div variants={itemVariants} className="mt-10 flex flex-col items-center gap-3 sm:flex-row">
          <motion.button
            {...buttonMotion}
            onClick={onViewMap}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-[0_1px_0_rgba(255,255,255,0.24)_inset,0_18px_60px_rgba(0,0,0,0.12)] transition hover:opacity-90"
          >
            View Live Map <ArrowRight className="h-4 w-4" />
          </motion.button>
<motion.a
  {...buttonMotion}
  href="#report"
  className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-border bg-background/45 px-5 text-sm font-semibold text-foreground/80 backdrop-blur transition hover:bg-foreground/5 hover:text-foreground"
>
  <Download className="h-4 w-4" /> Download Report
</motion.a>
        </motion.div>
      </motion.div>
    </section>
  );
}