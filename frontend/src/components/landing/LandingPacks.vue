<template>
  <section class="sec" id="packs">
    <div class="wrap">
      <div class="sec-head rv">
        <div class="sec-no"><b>03</b> Packs</div>
        <div>
          <h2>Four packs, each answering one committee question.</h2>
          <p>A tenant switches on what it needs. A housing society starts with Operations; a campus club starts with Voice. The mathematics underneath is the same code.</p>
        </div>
      </div>
      <table class="packs rv">
        <thead><tr><th>Pack</th><th>The question it answers</th><th>Modules</th><th>Status</th></tr></thead>
        <tbody>
          <tr>
            <td class="pk">01, Operations<small>request_flow</small></td>
            <td class="q">Is this getting better or worse, and is last week's dip a real shift or just noise?</td>
            <td><div class="tags"><span>survival</span><span>spc</span><span>queueing</span><span>changepoint</span></div></td>
            <td class="ship">Ships first</td>
          </tr>
          <tr>
            <td class="pk">03, Foresight<small>ledger, request_flow</small></td>
            <td class="q">What is coming, how sure are we, and was our last forecast actually any good?</td>
            <td><div class="tags"><span>forecast</span><span>calibration</span><span>conformal</span><span>drift</span></div></td>
            <td class="ship">Ships second</td>
          </tr>
          <tr>
            <td class="pk">04, Voice<small>decision, participation, signal</small></td>
            <td class="q">What does the community actually want, and whose voice is missing from the answer?</td>
            <td><div class="tags"><span>voting</span><span>budgeting</span><span>survey</span><span>network</span><span>privacy</span></div></td>
            <td class="ship">Ships third</td>
          </tr>
          <tr>
            <td class="pk">02, Comparison<small>all streams</small></td>
            <td class="q">Is the new vendor actually better, or did it just have a lucky month?</td>
            <td><div class="tags"><span>bayes</span><span>experiments</span><span>bandits</span></div></td>
            <td class="ship late">Last, needs history</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
