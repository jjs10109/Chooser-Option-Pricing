import unittest
import numpy as np
import pandas as pd
from option_iv.pricing import price, implied_vol
from option_iv.pipeline import date_splits
from option_iv.data import load

class PricingTests(unittest.TestCase):
    def test_bsm_reference_and_parity(self):
        args=dict(s=100,k=100,t=1,r=.05,q=0,sigma=.2,style="european")
        c=price(**args); p=price(**args,kind="put")
        self.assertAlmostEqual(c,10.45058357,places=6)
        self.assertAlmostEqual(c-p,100-100*np.exp(-.05),places=8)
    def test_crr_convergence_and_early_exercise(self):
        a=dict(s=100,k=100,t=1,r=.05,q=0,sigma=.2)
        self.assertLess(abs(price(**a,steps=800)-price(**a,style="european")),.01)
        self.assertGreater(price(**a,kind="put"),price(**a,kind="put",style="european"))
        b=dict(s=130,k=100,t=.5,r=.01,q=.15,sigma=.15)
        self.assertGreater(price(**b),price(**b,style="european"))
    def test_roundtrip_and_rejection(self):
        for style in ["american","european"]:
            for kind in ["call","put"]:
                a=dict(s=100,k=105,t=.7,r=.04,q=.02,style=style,kind=kind)
                self.assertAlmostEqual(implied_vol(price(sigma=.3,**a),**a),.3,places=5)
        with self.assertRaises(ValueError): implied_vol(1000,s=100,k=100,t=1,r=.04,q=0)
    def test_dividend_approximation(self):
        a=dict(s=100,k=100,t=1,r=.03,q=0,sigma=.25)
        self.assertLess(price(**a,cash_dividends=[(.5,3)]),price(**a))
        self.assertAlmostEqual(price(**a,cash_dividends=[]),price(**a))
    def test_split_groups_and_gap(self):
        df=pd.DataFrame({"quote_time":pd.date_range("2024-01-01",periods=20,tz="UTC").repeat(3)})
        for train,test in date_splits(df):
            self.assertGreater(df.iloc[test].quote_time.min()-df.iloc[train].quote_time.max(),pd.Timedelta(days=1))
            self.assertFalse(set(df.iloc[train].quote_time)&set(df.iloc[test].quote_time))
    def test_dividend_availability(self):
        from option_iv.dividends import trailing_yields
        df=pd.DataFrame({"symbol":["X"],"quote_time":pd.to_datetime(["2024-06-01"],utc=True),"spot":[100.]})
        div=pd.DataFrame({"symbol":["X","X","X"],"ex_date":pd.to_datetime(["2024-03-01","2024-09-01","2024-03-01"],utc=True),"known_at":pd.to_datetime(["2024-02-01","2024-05-01","2024-07-01"],utc=True),"amount":[1.,5.,9.]})
        self.assertEqual(trailing_yields(df,div),[.01])
    def test_future_macro_cannot_affect_past(self):
        import tempfile
        from pathlib import Path
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            for f in Path("data/sample").glob("*.csv"): shutil.copy(f,temp)
            before=load(temp)
            path=Path(temp)/"macro.csv"; macro=pd.read_csv(path)
            macro.loc[len(macro)]={"available_at":"2030-01-01T00:00:00Z","r":9,"vix":999,"term_spread":9}
            macro.to_csv(path,index=False)
            pd.testing.assert_frame_equal(before,load(temp))

if __name__=="__main__": unittest.main()
