/**
 * Guided tour — driver.js spotlight, case vocabulary only.
 * Pages set window.COMPLIANCE_TOUR_STEPS before this script runs, or use built-ins.
 */
(function () {
  const SEEN_KEY = "agrinexus_compliance_tour_seen";
  const START_EVENT = "compliance:start-tour";

  function presentSteps(steps) {
    return (steps || []).filter(function (s) {
      if (!s.element) return true;
      if (typeof s.element !== "string") return true;
      return !!document.querySelector(s.element);
    });
  }

  function addSkipButton(popover, d) {
    if (popover.footerButtons.querySelector(".tour-skip-btn")) return;
    const skip = document.createElement("button");
    skip.type = "button";
    skip.textContent = "Skip";
    skip.className = "driver-popover-prev-btn tour-skip-btn outturn-skip-btn";
    skip.addEventListener("click", function () {
      d.destroy();
    });
    popover.footerButtons.insertBefore(skip, popover.nextButton);
  }

  const PAGE_STEPS = {
    home: [
      {
        popover: {
          title: "What this tool is",
          description:
            "ESA label follow-through, one field at a time: plan the required practices, remind by text, confirm in plain language, keep a dated receipt — and show the cohort partner who followed through.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="home-hero"]',
        popover: {
          title: "You run the cohort",
          description:
            "A training class or an applicator business that stands behind its records. You care about a group of cases — not a single static form.",
        },
      },
      {
        element: '[data-tour="cohort-stats"]',
        popover: {
          title: "Follow-through at a glance",
          description:
            "How many planned, reminded, verified, or waiting for review. The legend under the strip defines each status.",
        },
      },
      {
        element: '[data-tour="cohort-board"]',
        popover: {
          title: "The case board",
          description:
            "Sample applicators for this demonstration. Open a row to see the reminder thread or a finished receipt.",
        },
      },
      {
        element: '[data-tour="roles"]',
        popover: {
          title: "Two roles, one loop",
          description:
            "Cohort partner watches the board. Applicator walks one case: plan, reply, keep the record. Next: Walk one case.",
        },
      },
    ],
    check: [
      {
        popover: {
          title: "Step 1 — Plan",
          description:
            "One question: can this applicator spray this Boone field with Liberty ULTRA? Points, weather, and bulletin actions — in plain language.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="summary"]',
        popover: {
          title: "Sample field pack",
          description:
            "Real EPA Reg. No. 7969-500 and a real bulletin for this farm, marked as sample educational data.",
        },
      },
      {
        element: '[data-tour="check-cta"]',
        popover: {
          title: "Check this plan",
          description:
            "Pick a calm or windy day to show the weather gate, then run the plan. Confirm and Receipt unlock after.",
        },
      },
    ],
    confirm: [
      {
        popover: {
          title: "Step 2 — Confirm",
          description:
            "Reminder out by text; applicator replies in their own words. Or use the checklist. Demo clock controls advance time for walkthroughs.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="sms-thread"]',
        popover: {
          title: "What they would text",
          description:
            "Reply in plain language — what was done on the field — not a one-click done.",
        },
      },
    ],
    receipt: [
      {
        popover: {
          title: "Step 3 — Receipt",
          description:
            "Standalone case record: status, points, weather, timeline, verification, and PDF download.",
          showButtons: ["next", "close"],
          showProgress: false,
          nextBtnText: "Show me",
          onPopoverRender: function (popover, opts) {
            addSkipButton(popover, opts.driver);
          },
        },
      },
      {
        element: '[data-tour="download-pdf"]',
        popover: {
          title: "Download the PDF",
          description: "The artifact that travels on its own.",
        },
      },
    ],
  };

  function getSteps() {
    if (window.COMPLIANCE_TOUR_STEPS && window.COMPLIANCE_TOUR_STEPS.length) {
      return presentSteps(window.COMPLIANCE_TOUR_STEPS);
    }
    const page = document.body.getAttribute("data-tour-page") || "home";
    return presentSteps(PAGE_STEPS[page] || PAGE_STEPS.home);
  }

  function startTour() {
    if (!window.driver || !window.driver.js || !window.driver.js.driver) {
      console.warn("driver.js not loaded");
      return;
    }
    const steps = getSteps();
    if (!steps.length) return;
    const d = window.driver.js.driver({
      showProgress: true,
      progressText: "{{current}} of {{total}}",
      allowClose: true,
      overlayColor: "#1a1714",
      overlayOpacity: 0.55,
      stagePadding: 6,
      stageRadius: 10,
      popoverClass: "outturn-tour",
      nextBtnText: "Next",
      prevBtnText: "Back",
      doneBtnText: "Done",
      onDestroyed: function () {
        try {
          localStorage.setItem(SEEN_KEY, "1");
        } catch (e) {
          /* ignore */
        }
      },
      steps: steps,
    });
    d.drive();
  }

  window.startComplianceTour = startTour;
  window.addEventListener(START_EVENT, startTour);

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-tour-trigger]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        startTour();
      });
    });

    var auto = document.body.getAttribute("data-tour-auto");
    if (auto === "false") return;
    var seen = "0";
    try {
      seen = localStorage.getItem(SEEN_KEY) || "0";
    } catch (e) {
      seen = "1";
    }
    if (seen === "1") return;
    if (window.innerWidth < 768) return;
    window.setTimeout(startTour, 700);
  });
})();
