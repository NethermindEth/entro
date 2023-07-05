class TestWriteObservation:
    # TODO: Add extra test fixtures and methods for oracles
    pass


"""
  describe('#increaseObservationCardinalityNext', () => {
    it('cannot be called before initialization', async () => {
      await expect(pool.increaseObservationCardinalityNext(2)).to.be.reverted
    })
    describe('after initialization', () => {
      beforeEach('initialize the pool', () => pool.initialize(encodePriceSqrt(1, 1)))
      it('oracle starting state after initialization', async () => {
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(1)
        const {
          secondsPerLiquidityCumulativeX128,
          tickCumulative,
          initialized,
          blockTimestamp,
        } = await pool.observations(0)
        expect(secondsPerLiquidityCumulativeX128).to.eq(0)
        expect(tickCumulative).to.eq(0)
        expect(initialized).to.eq(true)
        expect(blockTimestamp).to.eq(TEST_POOL_START_TIME)
      })
      it('increases observation cardinality next', async () => {
        await pool.increaseObservationCardinalityNext(2)
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(2)
      })
      it('is no op if target is already exceeded', async () => {
        await pool.increaseObservationCardinalityNext(5)
        await pool.increaseObservationCardinalityNext(3)
        const { observationCardinality, observationIndex, observationCardinalityNext } = await pool.slot0()
        expect(observationCardinality).to.eq(1)
        expect(observationIndex).to.eq(0)
        expect(observationCardinalityNext).to.eq(5)
      })
    })
  })

  describe('#setFeeProtocol', () => {
    beforeEach('initialize the pool', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
    })

    it('can only be called by factory owner', async () => {
      await expect(pool.connect(other).setFeeProtocol(5, 5)).to.be.reverted
    })
    it('fails if fee is lt 4 or gt 10', async () => {
      await expect(pool.setFeeProtocol(3, 3)).to.be.reverted
      await expect(pool.setFeeProtocol(6, 3)).to.be.reverted
      await expect(pool.setFeeProtocol(3, 6)).to.be.reverted
      await expect(pool.setFeeProtocol(11, 11)).to.be.reverted
      await expect(pool.setFeeProtocol(6, 11)).to.be.reverted
      await expect(pool.setFeeProtocol(11, 6)).to.be.reverted
    })
    it('succeeds for fee of 4', async () => {
      await pool.setFeeProtocol(4, 4)
    })
    it('succeeds for fee of 10', async () => {
      await pool.setFeeProtocol(10, 10)
    })
    it('sets protocol fee', async () => {
      await pool.setFeeProtocol(7, 7)
      expect((await pool.slot0()).feeProtocol).to.eq(119)
    })
    it('can change protocol fee', async () => {
      await pool.setFeeProtocol(7, 7)
      await pool.setFeeProtocol(5, 8)
      expect((await pool.slot0()).feeProtocol).to.eq(133)
    })
    it('can turn off protocol fee', async () => {
      await pool.setFeeProtocol(4, 4)
      await pool.setFeeProtocol(0, 0)
      expect((await pool.slot0()).feeProtocol).to.eq(0)
    })
    it('emits an event when turned on', async () => {
      await expect(pool.setFeeProtocol(7, 7)).to.be.emit(pool, 'SetFeeProtocol').withArgs(0, 0, 7, 7)
    })
    it('emits an event when turned off', async () => {
      await pool.setFeeProtocol(7, 5)
      await expect(pool.setFeeProtocol(0, 0)).to.be.emit(pool, 'SetFeeProtocol').withArgs(7, 5, 0, 0)
    })
    it('emits an event when changed', async () => {
      await pool.setFeeProtocol(4, 10)
      await expect(pool.setFeeProtocol(6, 8)).to.be.emit(pool, 'SetFeeProtocol').withArgs(4, 10, 6, 8)
    })
    it('emits an event when unchanged', async () => {
      await pool.setFeeProtocol(5, 9)
      await expect(pool.setFeeProtocol(5, 9)).to.be.emit(pool, 'SetFeeProtocol').withArgs(5, 9, 5, 9)
    })
  })

  describe('#lock', () => {
    beforeEach('initialize the pool', async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, minTick, maxTick, expandTo18Decimals(1))
    })

    it('cannot reenter from swap callback', async () => {
      const reentrant = (await (
        await ethers.getContractFactory('TestUniswapV3ReentrantCallee')
      ).deploy()) as TestUniswapV3ReentrantCallee

      // the tests happen in solidity
      await expect(reentrant.swapToReenter(pool.address)).to.be.revertedWith('Unable to reenter')
    })
  })

  describe('#snapshotCumulativesInside', () => {
    const tickLower = -TICK_SPACINGS[FeeAmount.MEDIUM]
    const tickUpper = TICK_SPACINGS[FeeAmount.MEDIUM]
    const tickSpacing = TICK_SPACINGS[FeeAmount.MEDIUM]
    beforeEach(async () => {
      await pool.initialize(encodePriceSqrt(1, 1))
      await mint(wallet.address, tickLower, tickUpper, 10)
    })
    it('throws if ticks are in reverse order', async () => {
      await expect(pool.snapshotCumulativesInside(tickUpper, tickLower)).to.be.reverted
    })
    it('throws if ticks are the same', async () => {
      await expect(pool.snapshotCumulativesInside(tickUpper, tickUpper)).to.be.reverted
    })
    it('throws if tick lower is too low', async () => {
      await expect(pool.snapshotCumulativesInside(getMinTick(tickSpacing) - 1, tickUpper)).be.reverted
    })
    it('throws if tick upper is too high', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower, getMaxTick(tickSpacing) + 1)).be.reverted
    })
    it('throws if tick lower is not initialized', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower - tickSpacing, tickUpper)).to.be.reverted
    })
    it('throws if tick upper is not initialized', async () => {
      await expect(pool.snapshotCumulativesInside(tickLower, tickUpper + tickSpacing)).to.be.reverted
    })
    it('is zero immediately after initialize', async () => {
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(0)
      expect(tickCumulativeInside).to.eq(0)
      expect(secondsInside).to.eq(0)
    })
    it('increases by expected amount when time elapses in the range', async () => {
      await pool.advanceTime(5)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('does not account for time increase above range', async () => {
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('does not account for time increase below range', async () => {
      await pool.advanceTime(5)
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(10))
      // tick is 0 for 5 seconds, then not in range
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('time increase below range is not counted', async () => {
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(1, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(7).shl(128).div(10))
      // tick is not in range then tick is 0 for 7 seconds
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(7)
    })
    it('time increase above range is not counted', async () => {
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(5)
      await swapToLowerPrice(encodePriceSqrt(1, 1), wallet.address)
      await pool.advanceTime(7)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(7).shl(128).div(10))
      expect((await pool.slot0()).tick).to.eq(-1) // justify the -7 tick cumulative inside value
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(-7)
      expect(secondsInside).to.eq(7)
    })
    it('positions minted after time spent', async () => {
      await pool.advanceTime(5)
      await mint(wallet.address, tickUpper, getMaxTick(tickSpacing), 15)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(8)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickUpper, getMaxTick(tickSpacing))
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(8).shl(128).div(15))
      // the tick of 2/1 is 6931
      // 8 seconds * 6931 = 55448
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(55448)
      expect(secondsInside).to.eq(8)
    })
    it('overlapping liquidity is aggregated', async () => {
      await mint(wallet.address, tickLower, getMaxTick(tickSpacing), 15)
      await pool.advanceTime(5)
      await swapToHigherPrice(encodePriceSqrt(2, 1), wallet.address)
      await pool.advanceTime(8)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(tickLower, tickUpper)
      expect(secondsPerLiquidityInsideX128).to.eq(BigNumber.from(5).shl(128).div(25))
      expect(tickCumulativeInside, 'tickCumulativeInside').to.eq(0)
      expect(secondsInside).to.eq(5)
    })
    it('relative behavior of snapshots', async () => {
      await pool.advanceTime(5)
      await mint(wallet.address, getMinTick(tickSpacing), tickLower, 15)
      const {
        secondsPerLiquidityInsideX128: secondsPerLiquidityInsideX128Start,
        tickCumulativeInside: tickCumulativeInsideStart,
        secondsInside: secondsInsideStart,
      } = await pool.snapshotCumulativesInside(getMinTick(tickSpacing), tickLower)
      await pool.advanceTime(8)
      // 13 seconds in starting range, then 3 seconds in newly minted range
      await swapToLowerPrice(encodePriceSqrt(1, 2), wallet.address)
      await pool.advanceTime(3)
      const {
        secondsPerLiquidityInsideX128,
        tickCumulativeInside,
        secondsInside,
      } = await pool.snapshotCumulativesInside(getMinTick(tickSpacing), tickLower)
      const expectedDiffSecondsPerLiquidity = BigNumber.from(3).shl(128).div(15)
      expect(secondsPerLiquidityInsideX128.sub(secondsPerLiquidityInsideX128Start)).to.eq(
        expectedDiffSecondsPerLiquidity
      )
      expect(secondsPerLiquidityInsideX128).to.not.eq(expectedDiffSecondsPerLiquidity)
      // the tick is the one corresponding to the price of 1/2, or log base 1.0001 of 0.5
      // this is -6932, and 3 seconds have passed, so the cumulative computed from the diff equals 6932 * 3
      expect(tickCumulativeInside.sub(tickCumulativeInsideStart), 'tickCumulativeInside').to.eq(-20796)
      expect(secondsInside - secondsInsideStart).to.eq(3)
      expect(secondsInside).to.not.eq(3)
    })
  })
  
"""
