<template>
  <section class="sec" id="spine">
    <div class="wrap">
      <div class="sec-head rv">
        <div class="sec-no"><b>01</b> Spine</div>
        <div>
          <h2>Six streams. Every statistic written once.</h2>
          <p>A society's complaint, a club's task and an NGO's volunteer request are one shape wearing three names. Quorum maps every vertical onto six canonical streams, so survival analysis is implemented once rather than once per community type.</p>
        </div>
      </div>
      <div class="bento rv">
        <div class="cell wide">
          <span class="idx">Stream 02, load-bearing</span>
          <h3>request_flow</h3>
          <p>Anything that opens, gets assigned, progresses and closes, carrying a category, an owner and timestamps. Complaints, maintenance jobs, club task boards, membership applications.</p>
          <div class="tags"><span>survival</span><span>spc</span><span>queueing</span><span>changepoint</span><span>conformal eta</span></div>
        </div>
        <div class="cell wide">
          <span class="idx">Stream 03</span>
          <h3>ledger</h3>
          <p>Signed money movements with a category and a counterparty. Maintenance dues, festival contributions, vendor payments, event budgets.</p>
          <div class="tags"><span>forecast</span><span>runway</span><span>benford</span><span>dp aggregates</span></div>
        </div>
        <div class="cell">
          <span class="idx">Stream 01</span>
          <h3>member_lifecycle</h3>
          <p>Join, activate, lapse, exit.</p>
          <div class="tags"><span>retention</span><span>churn risk</span></div>
        </div>
        <div class="cell">
          <span class="idx">Stream 04</span>
          <h3>participation</h3>
          <p>Attendance, RSVPs, volunteer hours, upvotes.</p>
          <div class="tags"><span>segmentation</span><span>network</span></div>
        </div>
        <div class="cell">
          <span class="idx">Stream 05</span>
          <h3>signal</h3>
          <p>Free text and ordinal ratings.</p>
          <div class="tags"><span>topics</span><span>near-dup</span><span>ordinal</span></div>
        </div>
        <div class="cell wide">
          <span class="idx">Stream 06</span>
          <h3>decision</h3>
          <p>Polls, ballots and budget allocations, with the social-choice disclosure most tools skip. When a poll contains a Condorcet cycle, the winner was chosen by the counting rule rather than by the community, and Quorum says so on the result page.</p>
          <div class="tags"><span>voting</span><span>participatory budgeting</span><span>representativeness</span></div>
        </div>
        <div class="cell wide">
          <span class="idx">Privacy floor</span>
          <h3>k_anonymity</h3>
          <p>Small communities are small. A per-block average over three households identifies those households, so any cell under five members is suppressed, including from the admin who asked for it.</p>
          <div class="tags"><span>k = 5</span><span>laplace noise</span></div>
        </div>
      </div>
    </div>
  </section>
</template>
